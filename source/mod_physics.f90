MODULE mod_physics

    USE mod_precision, ONLY: wp
    USE mod_types,     ONLY: SiteData, TurbineSpec, Individual, ConfigData
    
    IMPLICIT NONE
    PRIVATE

    ! Expose ONLY the top-level evaluation routine
    PUBLIC :: evaluate_aep
    public :: calculate_3d_wind_field

CONTAINS

    ! ==================================================================
    ! SUBROUTINE: evaluate_aep (Optimized Sparse Matrix Approach)
    ! ==================================================================
    SUBROUTINE evaluate_aep(ind, site, turbines, config)
        TYPE(Individual),  INTENT(INOUT) :: ind
        TYPE(SiteData),    INTENT(IN)    :: site
        TYPE(TurbineSpec), INTENT(IN)    :: turbines(:)
        TYPE(ConfigData),  INTENT(IN)    :: config

        INTEGER :: n_turb, i, m, t_step, t_type, n_idx, k_iter
        REAL(wp) :: total_aep, tep_farm, v_local, cp_val, area, m_ct
        REAL(wp), PARAMETER :: rho = 1.225_wp, pi = 3.141592653589793_wp

        ! --- SPARSE ARRAYS ---
        INTEGER, ALLOCATABLE  :: node_idx(:), type_turb(:), h_idx(:)
        REAL(wp), ALLOCATABLE :: ws_new(:), ws_old(:)
        REAL(wp), ALLOCATABLE :: wake_deficit(:), single_deficit(:)
        
        ! 1. Extract Active Turbines to Sparse Arrays (The Performance Fix)
        n_turb = COUNT(ind%chromosome > 1)
        IF (n_turb == 0) THEN
            ind%obj_vals(2) = 0.0_wp  
            RETURN
        END IF

        ALLOCATE(node_idx(n_turb), type_turb(n_turb), h_idx(n_turb))
        ALLOCATE(ws_new(n_turb), ws_old(n_turb))
        ALLOCATE(wake_deficit(n_turb), single_deficit(n_turb))

        ! Build the lookup tables
        m = 1
        DO i = 1, site%n_nodes
            t_type = ind%chromosome(i)
            IF (t_type > 1) THEN
                node_idx(m) = i
                type_turb(m) = ind%chromosome(i)
                h_idx(m)     = turbines(t_type)%h_idx
                m = m + 1
            END IF
        END DO

        total_aep = 0.0_wp

        ! --------------------------------------------------------------
        ! MAIN TIME-STEP LOOP
        ! --------------------------------------------------------------
        DO t_step = 1, site%nsteps
            
            ! Initialize local wind speeds for the active turbines ONLY
            DO m = 1, n_turb
                n_idx = node_idx(m)
                ws_new(m) = site%ws0_ts(n_idx, h_idx(m), t_step)
            END DO
            
            ! ----------------------------------------------------------
            ! ALL-TO-ALL ITERATIVE SOLVER (Sparse Logic)
            ! ----------------------------------------------------------
            DO k_iter = 1, config%max_iter 
                ws_old = ws_new 
                wake_deficit = 0.0_wp
                
                ! Loop 1: Calculate wakes produced by active turbines
                DO m = 1, n_turb
                    t_type = type_turb(m)
                    n_idx  = node_idx(m)
                    v_local = ws_new(m)
                    
                    m_ct = get_coeff(v_local, turbines(t_type)%v_ref, &
                                     turbines(t_type)%ct_ref, turbines(t_type)%n_points)
                    
                    ! ONLY calculate deficit AT the other turbine locations!
                    CALL bastankhah_wake_sparse(m, n_idx, turbines(t_type), m_ct, site, turbines, &
                                                n_turb, node_idx, type_turb, t_step, single_deficit)
                    
                    wake_deficit = wake_deficit + (single_deficit**2)
                END DO

                ! Loop 2: Apply the total aggregated wake
                DO m = 1, n_turb
                    IF (SQRT(wake_deficit(m)) < 1.0_wp) THEN
                        n_idx = node_idx(m)          
                        ! Multiply original free-stream by the wake fraction
                        ws_new(m) = site%ws0_ts(n_idx, h_idx(m), t_step) * (1.0_wp - SQRT(wake_deficit(m)))
                    ELSE
                        ws_new(m) = 0.0_wp
                    END IF
                END DO

                ! Convergence Check (comparing just the n_turb values)
                IF (MAXVAL(ABS(ws_new - ws_old)) < 1.0E-4_wp) EXIT 
            END DO 
            
            ! ----------------------------------------------------------
            ! Calculate power using the FINAL converged local speeds
            ! ----------------------------------------------------------
            tep_farm = 0.0_wp
            DO m = 1, n_turb
                t_type = type_turb(m)
                v_local = ws_new(m)
                
                cp_val = get_coeff(v_local, turbines(t_type)%v_ref, &
                                   turbines(t_type)%cp_ref, turbines(t_type)%n_points)
                
                area = pi * (turbines(t_type)%rotor_diameter / 2.0_wp)**2
                tep_farm = tep_farm + (0.5_wp * rho * area * (v_local**3) * cp_val)
            END DO
            
            total_aep = total_aep + tep_farm
        END DO

        total_aep = total_aep / REAL(site%nsteps, wp)
        ind%obj_vals(2) = -total_aep

        DEALLOCATE(node_idx, type_turb, ws_new, ws_old, wake_deficit, single_deficit)

    END SUBROUTINE evaluate_aep

    ! ==================================================================
    ! SUBROUTINE: bastankhah_wake_sparse
    ! (Strict mathematical port of original F77 logic)
    ! ==================================================================
    SUBROUTINE bastankhah_wake_sparse(m, n_idx, t_spec, m_ct1, site, turbines, &
                                      n_turb, node_idx, type_turb, t_step, deficit)
        TYPE(SiteData),    INTENT(IN)  :: site
        TYPE(TurbineSpec), INTENT(IN)  :: turbines(:)
        TYPE(TurbineSpec), INTENT(IN)  :: t_spec
        INTEGER,           INTENT(IN)  :: m, n_idx, n_turb, t_step
        INTEGER,           INTENT(IN)  :: node_idx(:), type_turb(:)
        REAL(wp),          INTENT(IN)  :: m_ct1
        REAL(wp),          INTENT(OUT) :: deficit(:) ! Now a 1D array of size n_turb
        
        REAL(wp), PARAMETER :: k_star = 0.0324_wp 
        
        REAL(wp) :: beta, hubX, hubY, theta, d_wake, h_wake
        REAL(wp) :: dx, dy, x_rot, y_rot, x_rel
        REAL(wp) :: radial_dist, sigma_d0, a1, b1, c1, c2, z_coord
        INTEGER  :: i, j_node, j_type
        real(wp) :: m_ct
        
        ! 1. Initialize output deficit array to zero
        deficit = 0.0_wp
        
        ! 2. Get properties of the wake-producing turbine (m)
        hubX   = site%x_coord(n_idx)
        hubY   = site%y_coord(n_idx)
        theta  = site%wd0_ts(n_idx, t_step)
        d_wake = t_spec%rotor_diameter
        h_wake = t_spec%hub_height
        m_ct = MAX(0.0001_wp, MIN(m_ct1, 0.9999_wp))
        ! 3. Calculate beta
        ! (Using MAX to prevent NaN if m_ct somehow hits 1.0)
        beta = 0.5_wp * ((1.0_wp + SQRT(1.0_wp - m_ct)) / SQRT(1.0_wp - m_ct))
                                   

        ! 4. Loop through ONLY the downstream active turbines
        DO i = 1, n_turb
            ! A turbine cannot wake itself
            IF (i == m) CYCLE
            
            j_node = node_idx(i)
            
            ! 5. Calculate rotated coordinates (Exact match to old script)
            dx = site%x_coord(j_node) - hubX
            dy = site%y_coord(j_node) - hubY
            x_rot =  dx * COS(theta) + dy * SIN(theta)
            y_rot = -dx * SIN(theta) + dy * COS(theta)
            
            radial_dist = ABS(y_rot)
            x_rel = MAX(x_rot, 0.0_wp)
            
            ! 6. Logic Gates: Downstream AND within 3 diameters
            IF (x_rel > 1.0_wp .AND. radial_dist < (3.0_wp * d_wake)) THEN
                
                ! Calculate normalized wake diameter
                sigma_d0 = (k_star * x_rel / d_wake) + (0.2_wp * SQRT(beta))
                
                ! Pre-calculate Gaussian terms
                a1 = m_ct / (8.0_wp * (sigma_d0 ** 2))
                
                ! --- ANTI-NaN NEAR-WAKE CAP (Restored exactly) ---
                IF (a1 >= 1.0_wp) a1 = 0.999_wp
                
                b1 = -1.0_wp / (2.0_wp * (sigma_d0 ** 2))
                c2 = (radial_dist / d_wake) ** 2
                
                ! 7. Calculate height difference specifically for the target turbine
                j_type  = type_turb(i)
                z_coord = turbines(j_type)%hub_height
                c1 = ((z_coord - h_wake) / d_wake) ** 2
                
                ! 8. Apply exact deficit formula
                deficit(i) = (1.0_wp - SQRT(1.0_wp - a1)) * EXP(b1 * (c1 + c2))
                
            END IF
        END DO
    END SUBROUTINE bastankhah_wake_sparse

    ! ==================================================================
    ! SUBROUTINE: bastankhah_wake_dense
    ! Calculates the wake deficit across ALL nodes and ALL height levels
    ! ==================================================================
    SUBROUTINE bastankhah_wake_dense(n_idx, t_spec, m_ct1, site, t_step, deficit)
        TYPE(SiteData),    INTENT(IN)  :: site
        TYPE(TurbineSpec), INTENT(IN)  :: t_spec
        INTEGER,           INTENT(IN)  :: n_idx, t_step
        REAL(wp),          INTENT(IN)  :: m_ct1
        REAL(wp),          INTENT(OUT) :: deficit(:,:) ! 2D: (n_nodes, n_hlevels)
        
        REAL(wp), PARAMETER :: k_star = 0.0324_wp
        
        REAL(wp) :: beta, hubX, hubY, theta, d_wake, h_wake
        REAL(wp) :: dx, dy, x_rot, y_rot, x_rel
        REAL(wp) :: radial_dist, sigma_d0, a1, b1, c1, c2, z_coord
        INTEGER  :: i, j

        real(wp) :: m_ct
        
        ! 1. Initialize output deficit array to zero
        deficit = 0.0_wp
        
        ! 2. Get properties of the wake-producing turbine
        hubX   = site%x_coord(n_idx)
        hubY   = site%y_coord(n_idx)
        theta  = site%wd0_ts(n_idx, t_step)
        d_wake = t_spec%rotor_diameter
        h_wake = t_spec%hub_height
        m_ct = MAX(0.0001_wp, MIN(m_ct1, 0.9999_wp))
        ! 3. Calculate beta
        beta = 0.5_wp * ((1.0_wp + SQRT(1.0_wp - m_ct)) / SQRT(1.0_wp - m_ct))

        ! 4. Loop through EVERY node in the grid
        DO i = 1, site%n_nodes
            
            ! 5. Calculate rotated coordinates
            dx = site%x_coord(i) - hubX
            dy = site%y_coord(i) - hubY
            x_rot =  dx * COS(theta) + dy * SIN(theta)
            y_rot = -dx * SIN(theta) + dy * COS(theta)
            
            radial_dist = ABS(y_rot)
            x_rel = MAX(x_rot, 0.0_wp)
            
            ! 6. Logic Gates: Downstream AND within 3 diameters
            IF (x_rel > 1.0_wp .AND. radial_dist < (3.0_wp * d_wake)) THEN
                
                sigma_d0 = (k_star * x_rel / d_wake) + (0.2_wp * SQRT(beta))
                a1 = m_ct / (8.0_wp * (sigma_d0 ** 2))
                
                IF (a1 >= 1.0_wp) a1 = 0.999_wp
                
                b1 = -1.0_wp / (2.0_wp * (sigma_d0 ** 2))
                c2 = (radial_dist / d_wake) ** 2
                
                ! 7. Calculate deficit for EVERY height level at this node
                DO j = 1, site%n_hlevel
                    z_coord = site%h_level(j)
                    c1 = ((z_coord - h_wake) / d_wake) ** 2
                    
                    deficit(i, j) = (1.0_wp - SQRT(1.0_wp - a1)) * EXP(b1 * (c1 + c2))
                END DO
            END IF
        END DO
    END SUBROUTINE bastankhah_wake_dense

    ! ==================================================================
    ! SUBROUTINE: calculate_3d_wind_field
    ! Solves the full 3D wind field for visualization/post-processing
    ! ==================================================================
    SUBROUTINE calculate_3d_wind_field(ind, site, turbines, config, ws_out)
        TYPE(Individual),  INTENT(IN)  :: ind
        TYPE(SiteData),    INTENT(IN)  :: site
        TYPE(TurbineSpec), INTENT(IN)  :: turbines(:)
        TYPE(ConfigData),  INTENT(IN)  :: config
        REAL(wp), ALLOCATABLE, INTENT(OUT) :: ws_out(:,:,:) ! (nodes, h_levels, t_steps)

        INTEGER  :: n_turb, i, j, m, t_step, t_type, n_idx, k_iter
        REAL(wp) :: v_local, m_ct

        ! --- SPARSE ARRAYS (For the wake producers) ---
        INTEGER, ALLOCATABLE :: node_idx(:), type_turb(:), h_idx(:)
        
        ! --- DENSE ARRAYS (For the grid convergence) ---
        REAL(wp), ALLOCATABLE :: ws_new(:,:), ws_old(:,:)
        REAL(wp), ALLOCATABLE :: wake_deficit(:,:), single_deficit(:,:)
        
        ! 1. Extract Active Turbines to Sparse Arrays
        n_turb = COUNT(ind%chromosome > 1)
        
        ! Allocate the master output array
        ALLOCATE(ws_out(site%n_nodes, site%n_hlevel, site%nsteps))

        ! Handle Edge Case: Completely empty layout
        IF (n_turb == 0) THEN
            ws_out = site%ws0_ts  ! Wind is completely undisturbed
            RETURN
        END IF

        ALLOCATE(node_idx(n_turb), type_turb(n_turb), h_idx(n_turb))
        ALLOCATE(ws_new(site%n_nodes, site%n_hlevel))
        ALLOCATE(ws_old(site%n_nodes, site%n_hlevel))
        ALLOCATE(wake_deficit(site%n_nodes, site%n_hlevel))
        ALLOCATE(single_deficit(site%n_nodes, site%n_hlevel))

        ! Build the lookup tables for the wake producers
        m = 1
        DO i = 1, site%n_nodes
            t_type = ind%chromosome(i)
            IF (t_type > 1) THEN
                node_idx(m)  = i
                type_turb(m) = t_type
                h_idx(m)     = turbines(t_type)%h_idx 
                m = m + 1
            END IF
        END DO

        ! --------------------------------------------------------------
        ! MAIN TIME-STEP LOOP
        ! --------------------------------------------------------------
        DO t_step = 1, site%nsteps
            
            ! Initialize the dense wind field for this time step
            ws_new = site%ws0_ts(:,:,t_step)
            
            ! ----------------------------------------------------------
            ! ALL-TO-ALL ITERATIVE SOLVER
            ! ----------------------------------------------------------
            DO k_iter = 1, config%max_iter 
                ws_old = ws_new 
                wake_deficit = 0.0_wp
                
                ! Loop 1: Calculate wakes produced by active turbines
                DO m = 1, n_turb
                    t_type = type_turb(m)
                    n_idx  = node_idx(m)
                    
                    ! Local wind speed specifically at the turbine's hub
                    v_local = ws_new(n_idx, h_idx(m))
                    
                    m_ct = get_coeff(v_local, turbines(t_type)%v_ref, &
                                     turbines(t_type)%ct_ref, turbines(t_type)%n_points)
                    
                    ! Calculate dense deficit field
                    CALL bastankhah_wake_dense(n_idx, turbines(t_type), m_ct, site, t_step, single_deficit)
                    
                    wake_deficit = wake_deficit + (single_deficit**2)
                END DO

                ! Loop 2: Apply the total aggregated wake to the ENTIRE grid
                DO i = 1, site%n_nodes
                    DO j = 1, site%n_hlevel
                        IF (SQRT(wake_deficit(i, j)) < 1.0_wp) THEN
                            ws_new(i, j) = site%ws0_ts(i, j, t_step) * (1.0_wp - SQRT(wake_deficit(i, j)))
                        ELSE
                            ws_new(i, j) = 0.0_wp
                        END IF
                    END DO
                END DO

                ! Convergence Check (comparing the dense grid)
                IF (MAXVAL(ABS(ws_new - ws_old)) < 1.0E-4_wp) EXIT 
            END DO 
            
            ! Store the converged 3D slice for this time step
            ws_out(:,:,t_step) = ws_new
        END DO

        DEALLOCATE(node_idx, type_turb, h_idx)
        DEALLOCATE(ws_new, ws_old, wake_deficit, single_deficit)

    END SUBROUTINE calculate_3d_wind_field

    ! ==================================================================
    ! HELPER FUNCTIONS
    ! ==================================================================
    FUNCTION get_coeff(v_in, v_ref, c_ref, n_pts) RESULT(coeff)
        REAL(wp), INTENT(IN) :: v_in
        REAL(wp), INTENT(IN) :: v_ref(:), c_ref(:)
        INTEGER,  INTENT(IN) :: n_pts
        REAL(wp) :: coeff, frac
        INTEGER :: i

        coeff = 0.0_wp
        IF (v_in < v_ref(1) .OR. v_in > v_ref(n_pts)) RETURN

        DO i = 1, n_pts - 1
            IF (v_in >= v_ref(i) .AND. v_in <= v_ref(i+1)) THEN
                frac = (v_in - v_ref(i)) / (v_ref(i+1) - v_ref(i))
                coeff = c_ref(i) + frac * (c_ref(i+1) - c_ref(i))
                RETURN
            END IF
        END DO
    END FUNCTION get_coeff

END MODULE mod_physics
