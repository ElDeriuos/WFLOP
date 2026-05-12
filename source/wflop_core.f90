MODULE precision
    USE, INTRINSIC :: iso_fortran_env, ONLY: real64
    IMPLICIT NONE
    
    ! Define 'wp' (Working Precision) as standard 64-bit float.
    ! Usage: REAL(wp) :: my_variable
    INTEGER, PARAMETER :: wp = real64

END MODULE precision

MODULE types
    USE precision, ONLY: wp
    IMPLICIT NONE

    ! ==================================================================
    ! 1. CONFIGURATION DATA
    ! Holds parameters read from 'config.inp' or the GUI
    ! ==================================================================
    TYPE :: ConfigData
        INTEGER  :: it_max       ! Maximum generations
        INTEGER  :: n_pop        ! Population size
        REAL(wp) :: p_cross      ! Crossover probability
        REAL(wp) :: p_mut        ! Mutation probability
        REAL(wp) :: mu           ! Mutation intensity
        INTEGER  :: max_turbs    ! Maximum allowable turbines
        INTEGER  :: min_turbs    ! Minimum allowable turbines
        INTEGER  :: n_obj        ! Number of objectives (1 or 2+)
        INTEGER  :: max_iter     ! Maximum iterations for All2AllIterative
        INTEGER  :: farmlifetime ! Estimated Farm's Life Time (Year)
        INTEGER, ALLOCATABLE :: lb(:)  ! Lower bounds for each gene (node)
        INTEGER, ALLOCATABLE :: ub(:)  ! Upper bounds for each gene (node)
        REAL(wp) :: workability   ! The percentage of time the weather allows construction
        
        INTEGER  :: opt_mode     ! 1 = SOGA, 2 = MOGA
        INTEGER  :: obj_1        ! SOGA target, or MOGA Objective 1
        INTEGER  :: obj_2        ! MOGA Objective 2 (Ignored if SOGA)
        ! --- File Paths ---
        CHARACTER(LEN=512) :: f_turb
        CHARACTER(LEN=512) :: f_wind
        CHARACTER(LEN=512) :: f_bathy
        CHARACTER(LEN=512) :: f_dist
        CHARACTER(LEN=512) :: out_dir
    END TYPE ConfigData

    ! ==================================================================
    ! 2. SITE & MESH DATA
    ! Holds the static physical layout and meteorological data
    ! ==================================================================
    TYPE :: SiteData
        INTEGER :: n_nodes       ! Total grid nodes
        INTEGER :: n_hlevel      ! Number of unique height levels
        INTEGER :: nsteps        ! Total time steps in wind data
        integer :: n_types       ! Number of turbine types available (including dummy)
        real(wp):: d_landfall    ! Distance from landfall (km)
        real(wp):: d_shore       ! Distance from shore (km)
        real(wp):: d_port        ! Distance from nearest port (km)
        
        ! Spatial coordinates (Allocatable arrays)
        REAL(wp), ALLOCATABLE :: x_coord(:) 
        REAL(wp), ALLOCATABLE :: y_coord(:)
        REAL(wp), ALLOCATABLE :: z_coord(:)
        REAL(wp), ALLOCATABLE :: h_level(:) ! The unique height values (m)

        ! Wind Time-Series: Dimensions (node, height_level, time_step)
        REAL(wp), ALLOCATABLE :: ws0_ts(:,:,:) ! Free-stream wind speed
        REAL(wp), ALLOCATABLE :: wd0_ts(:,:)   ! Free-stream wind direction
    END TYPE SiteData

    ! ==================================================================
    ! 3. TURBINE SPECIFICATION
    ! Holds the physical and aerodynamic data for a single turbine type
    ! ==================================================================
    TYPE :: TurbineSpec
        REAL(wp) :: rated_power
        REAL(wp) :: rotor_diameter
        REAL(wp) :: hub_height
        REAL(wp) :: cut_in
        REAL(wp) :: cut_off
        INTEGER  :: h_idx
        
        ! Interpolation tables for Cp and Ct
        INTEGER  :: n_points               ! Number of valid curve points
        REAL(wp), ALLOCATABLE :: v_ref(:)  ! Reference wind speeds
        REAL(wp), ALLOCATABLE :: cp_ref(:) ! Power coefficient curve
        REAL(wp), ALLOCATABLE :: ct_ref(:) ! Thrust coefficient curve
    END TYPE TurbineSpec

    ! ==================================================================
    ! 4. THE INDIVIDUAL (A single Wind Farm Layout)
    ! Represents one solution in the Genetic Algorithm
    ! ==================================================================
    TYPE :: Individual
        INTEGER,  ALLOCATABLE :: chromosome(:) ! The gene array (length = n_nodes)
        
        ! --- RAW METRICS  ---
        REAL(wp)              :: raw_cost      ! Pure financial Cost
        REAL(wp)              :: raw_aep       ! Pure Annual Energy Production
        real(wp)              :: raw_fatigue   ! Maximum fatigue load (to be added later)
        REAL(wp)              :: fitness       ! Scalar fitness score used ONLY by SOGA
        
        ! --- NSGA-II METRICS ---
        REAL(wp), ALLOCATABLE :: obj_vals(:)   ! Objective outputs for NSGA-II
        INTEGER               :: rank          ! NSGA-II non-domination front
        REAL(wp)              :: distance      ! NSGA-II crowding distance
        LOGICAL               :: is_valid      ! .FALSE. if constraints are violated
    END TYPE Individual

    ! ==================================================================
    ! 5. THE POPULATION
    ! A collection of Individuals
    ! ==================================================================
    TYPE :: Population
        TYPE(Individual), ALLOCATABLE :: inds(:)
    END TYPE Population

END MODULE types

MODULE inputs

    USE precision, ONLY: wp
    USE types,     ONLY: ConfigData, SiteData, TurbineSpec, Population

        
    IMPLICIT NONE
    PRIVATE   ! Hide everything by default

    ! Only allow the main program to call these specific subroutines
    PUBLIC :: read_gui_config
    PUBLIC :: load_site_data
    PUBLIC :: load_turbines

CONTAINS

    ! ==================================================================
    ! SUBROUTINE 1: Read the GUI configuration
    ! ==================================================================
    SUBROUTINE read_gui_config(filename, config)
        CHARACTER(LEN=*), INTENT(IN)  :: filename
        TYPE(ConfigData), INTENT(OUT) :: config
        INTEGER :: f_unit, ios

        ! NEW: Use 'NEWUNIT' to automatically assign a safe, unused file number
        OPEN(NEWUNIT=f_unit, FILE=filename, STATUS='OLD', ACTION='READ', IOSTAT=ios)
        
        IF (ios /= 0) THEN
            PRINT *, "🔴 ERROR: Could not open configuration file: ", TRIM(filename)
            STOP 1
        END IF

        ! Read the exact order exported by your Python GUI
        READ(f_unit, *) config%it_max
        READ(f_unit, *) config%n_pop
        READ(f_unit, *) config%p_cross
        READ(f_unit, *) config%p_mut
        READ(f_unit, *) config%mu
        READ(f_unit, *) config%max_turbs
        READ(f_unit, *) config%min_turbs
        READ(f_unit, *) config%workability
        
        READ(f_unit, *) config%opt_mode
        READ(f_unit, *) config%obj_1
        READ(f_unit, *) config%obj_2
        
        ! Read File Paths
        READ(f_unit, *) config%f_turb
        READ(f_unit, *) config%f_wind
        READ(f_unit, *) config%f_bathy
        READ(f_unit, *) config%f_dist
        READ(f_unit, *) config%out_dir
        ! READ(f_unit, *) config%max_iter
        CLOSE(f_unit)

        ! Default
        config%n_obj = 2
        config%max_iter = 10
        config%farmlifetime = 25
        PRINT *, "Configuration loaded successfully."
        
    END SUBROUTINE read_gui_config

    ! ==================================================================
    ! SUBROUTINE 2: Load Turbines and extract unique height levels
    ! ==================================================================
    SUBROUTINE load_turbines(filename, turbines, site)
        CHARACTER(LEN=*),               INTENT(IN)    :: filename
        TYPE(TurbineSpec), ALLOCATABLE, INTENT(OUT)   :: turbines(:)
        TYPE(SiteData),                 INTENT(INOUT) :: site  ! Passed in to store heights
        
        INTEGER :: f_unit, ios, nd_turbs, i, j
        CHARACTER(LEN=512) :: curve_path
        
        ! Temporary array to find unique heights (assuming max 100 types)
        REAL(wp) :: temp_h(100), current_h
        LOGICAL  :: is_unique

        OPEN(NEWUNIT=f_unit, FILE=filename, STATUS='OLD', ACTION='READ', IOSTAT=ios)
        IF (ios /= 0) STOP "🔴 ERROR: Missing turbine_spec.txt"

        READ(f_unit, *) 
        READ(f_unit, *) site%n_types
        nd_turbs = 1  ! Dummy turbine
        site%n_types = site%n_types + nd_turbs 
        
        READ(f_unit, *) 
        READ(f_unit, *) 

        ALLOCATE(turbines(site%n_types))
        site%n_hlevel = 0

        do i = 1, nd_turbs
            turbines(i)%rotor_diameter = 0.0_wp
            turbines(i)%rated_power    = 0.0_wp
            turbines(i)%hub_height     = 0.0_wp
            turbines(i)%h_idx          = 0 ! Safe dummy index
            turbines(i)%n_points       = 0
        end do

        DO i = (nd_turbs + 1), site%n_types
            READ(f_unit, *) turbines(i)%rotor_diameter, turbines(i)%rated_power, &
                            turbines(i)%cut_in, turbines(i)%cut_off, turbines(i)%hub_height
            
            READ(f_unit, '(A)') curve_path
            CALL read_turbine_curve(TRIM(curve_path), turbines(i))
            
            ! ----------------------------------------------------------
            ! LOGIC CHECK: Find Unique Height Levels
            ! ----------------------------------------------------------
            current_h = turbines(i)%hub_height
            
            IF (site%n_hlevel == 0) THEN
                ! The very first turbine automatically sets the first height
                site%n_hlevel = 1
                temp_h(1) = current_h
            ELSE
                ! For all subsequent turbines, check against the known list
                is_unique = .TRUE.
                DO j = 1, site%n_hlevel
                    ! Using a 1mm tolerance check for floating point safety
                    IF (ABS(temp_h(j) - current_h) < 1.0E-3_wp) THEN
                        is_unique = .FALSE.
                        EXIT
                    END IF
                END DO
                
                ! If it wasn't found in the list, add it
                IF (is_unique) THEN
                    site%n_hlevel = site%n_hlevel + 1
                    temp_h(site%n_hlevel) = current_h
                END IF
            END IF
        END DO
        CLOSE(f_unit)

        ! Now that we know exactly how many unique heights exist, 
        ! allocate the site array and copy the values over.
        ALLOCATE(site%h_level(site%n_hlevel))
        site%h_level(1:site%n_hlevel) = temp_h(1:site%n_hlevel)

        DO i = (nd_turbs + 1), site%n_types
            DO j = 1, site%n_hlevel
                IF (ABS(turbines(i)%hub_height - site%h_level(j)) < 1.0E-3_wp) THEN
                    turbines(i)%h_idx = j
                    EXIT
                END IF
            END DO
        END DO

        PRINT *, "Loaded ", site%n_types - 1, " real turbine profiles."
        PRINT *, "Found ", site%n_hlevel, " unique hub height level(s)."

    END SUBROUTINE load_turbines

    ! ==================================================================
    ! SUBROUTINE 3: Load Mesh, Bathymetry, and Wind Data
    ! ==================================================================
    SUBROUTINE load_site_data(file_wind, file_depth, file_shore, site, config)
        CHARACTER(LEN=*), INTENT(IN) :: file_wind, file_depth, file_shore
        TYPE(ConfigData), INTENT(INOUT) :: config
        TYPE(SiteData), INTENT(INOUT) :: site

        INTEGER :: f_unit, ios, dummy_int, i
        ! Temporary variables for reading
        REAL(wp) :: dummy_real
        REAL(wp) :: u_val, v_val, ws_mag, wd_rad
        INTEGER  :: t_step, j
        REAL(wp), PARAMETER :: PI = 3.141592653589793_wp
        ! The power law exponent (alpha). 1/7 is a standard value.
        REAL(wp), PARAMETER :: alpha = 1.0 / 7.0

        PRINT *, "Loading site data (this may take a moment)..."

        ! 1. Read the wind data header to get dimensions
        OPEN(NEWUNIT=f_unit, FILE=file_wind, STATUS='OLD', IOSTAT=ios)
        IF (ios /= 0) STOP "🔴 ERROR: Missing filtered_wind.txt"
        
        READ(f_unit, *) ! Skip headers
        READ(f_unit, *) 
        READ(f_unit, *) site%n_nodes, site%nsteps

        ! 2. DYNAMIC MEMORY: Allocate coordinate arrays now that we know n_nodes
        ALLOCATE(site%x_coord(site%n_nodes))
        ALLOCATE(site%y_coord(site%n_nodes))
        ALLOCATE(site%z_coord(site%n_nodes))
        ! Allocate bounds based on the total number of grid nodes
        ALLOCATE(config%lb(site%n_nodes))
        ALLOCATE(config%ub(site%n_nodes))

        ! By default, allow the Dummy Turbine (1) up to the Maximum Turbine Type
        DO i = 1, site%n_nodes
            config%lb(i) = 1
            config%ub(i) = site%n_types
        END DO

        ! Read coordinates directly from this file
        DO i = 1, site%n_nodes
            READ(f_unit, *) dummy_int, site%x_coord(i), site%y_coord(i)
        END DO
        
        ! --------------------------------------------------------------
        ! 3. DYNAMIC MEMORY: Allocate Wind Time-Series Arrays
        ! --------------------------------------------------------------
        ! print*, site%n_nodes, site%n_hlevel, site%nsteps
        ALLOCATE(site%ws0_ts(site%n_nodes, site%n_hlevel, site%nsteps))
        ALLOCATE(site%wd0_ts(site%n_nodes, site%nsteps))        
        ! --------------------------------------------------------------
        ! 4. Parse the Time Series Data
        ! --------------------------------------------------------------
        DO t_step = 1, site%nsteps
            ! Your Python script writes the time step index first (e.g., "     1")
            READ(f_unit, *) dummy_int 
            
            DO i = 1, site%n_nodes
                ! Read the U and V components for this specific node
                READ(f_unit, *) u_val, v_val
                
                ! Calculate wind speed magnitude
                ws_mag = SQRT((u_val**2) + (v_val**2))
                
                ! Calculate wind direction (Meteorological convention from North)
                wd_rad = ATAN2(u_val, v_val)
                IF (wd_rad < 0.0_wp) wd_rad = wd_rad + (2.0_wp * PI)
                
                site%wd0_ts(i, t_step) = wd_rad

                ! Power Law 
                DO j = 1, site%n_hlevel
                    site%ws0_ts(i, j, t_step) = ws_mag * ((site%h_level(j) / 10.0_wp) ** alpha)
                END DO
            END DO
        END DO
        
        CLOSE(f_unit)

        OPEN(NEWUNIT=f_unit, FILE=file_shore, STATUS='OLD', IOSTAT=ios)
        read(f_unit, *) site%d_shore, site%d_landfall, site%d_port
        CLOSE(f_unit)

        PRINT *, "✅ Site spatial and wind data loaded."

        ! --------------------------------------------------------------
        ! 5. Read Bathymetry (Depth)
        ! --------------------------------------------------------------
        OPEN(NEWUNIT=f_unit, FILE=file_depth, STATUS='OLD', IOSTAT=ios)
        IF (ios /= 0) STOP "🔴 ERROR: Missing farm_bathymetry.dat"
        
        do i= 1, 9
            READ(f_unit, *) ! Skip headers
        end do
        DO i = 1, site%n_nodes
            READ(f_unit, *) dummy_real, dummy_real, site%z_coord(i)
        END DO
        CLOSE(f_unit)

    END SUBROUTINE load_site_data
    ! ==================================================================
    ! PRIVATE HELPER ROUTINES
    ! ==================================================================
    SUBROUTINE read_turbine_curve(filepath, t_spec)
        CHARACTER(LEN=*),  INTENT(IN)    :: filepath
        TYPE(TurbineSpec), INTENT(INOUT) :: t_spec
        
        INTEGER  :: u, ios, count, i
        REAL(wp) :: dummy_p, dummy_t
        
        OPEN(NEWUNIT=u, FILE=filepath, STATUS='OLD', ACTION='READ', IOSTAT=ios)
        IF (ios /= 0) THEN
            PRINT *, "🔴 ERROR: Cannot open curve file: ", TRIM(filepath)
            STOP 1
        END IF
        
        READ(u, *) ! Skip header line
        ! 1. Scan the file to count the exact number of data points
        count = 0
        DO
            ! Read a line. If we hit End-Of-File (ios < 0), exit the loop.
            READ(u, *, IOSTAT=ios) 
            IF (ios < 0) EXIT
            IF (ios > 0) STOP "🔴 ERROR: Formatting issue in curve file."
            count = count + 1
        END DO
        
        t_spec%n_points = count
        
        ! 2. Dynamically allocate the exact memory needed for this turbine's curves
        ALLOCATE(t_spec%v_ref(count))
        ALLOCATE(t_spec%cp_ref(count))
        ALLOCATE(t_spec%ct_ref(count))
        
        ! 3. Rewind the file back to the very first line
        REWIND(u)
        read(u, *) ! Skip header line again before reading data
        
        ! 4. Read the actual data
        DO i = 1, count
            ! Assuming columns: 1=WindSpeed, 2=Power, 3=Cp, 4=Thrust, 5=Ct
            ! We read Power and Thrust into dummy variables since we only strictly need Cp and Ct
            READ(u, *) t_spec%v_ref(i), dummy_p, t_spec%cp_ref(i), dummy_t, t_spec%ct_ref(i)
        END DO
        
        CLOSE(u)
    END SUBROUTINE read_turbine_curve

END MODULE inputs

MODULE costs

    USE precision, ONLY: wp
    USE types,     ONLY: SiteData, TurbineSpec, Individual, ConfigData

    IMPLICIT NONE
    PRIVATE

    ! Expose ONLY the top-level evaluation routine
    PUBLIC :: evaluate_financial_cost

    ! --- Wind Turbine (WT) Cost Coefficients (Kikuchi Table 5) ---
    REAL(wp), PARAMETER :: CWT1 = 78300.0_wp   
    REAL(wp), PARAMETER :: CWT2 = 717000.0_wp  
    REAL(wp), PARAMETER :: CWT3 = -190000.0_wp 
    REAL(wp), PARAMETER :: CWT4 = 2330000.0_wp 
    REAL(wp), PARAMETER :: CWT5 = 1000000.0_wp 

    ! --- Support Structure (SS) Cost Constants (Kikuchi Table 6) ---
    REAL(wp), PARAMETER :: RHO_STEEL  = 7870.0_wp  ! Density (kg/m3)
    REAL(wp), PARAMETER :: C_SS_STEEL = 0.91_wp    ! Raw steel cost (GBP/kg)
    REAL(wp), PARAMETER :: C_SS_PROD  = 2.69_wp    ! Manufacturing cost (GBP/kg)
    REAL(wp), PARAMETER :: A_SS1 = 0.001_wp        ! Thickness coefficient 1
    REAL(wp), PARAMETER :: A_SS2 = 0.05_wp         ! Thickness coefficient 2
    REAL(wp), PARAMETER :: A_SS3 = 1.65_wp         ! Length coefficient 1
    REAL(wp), PARAMETER :: A_SS4 = 21.0_wp         ! Length coefficient 2
    REAL(wp), PARAMETER :: PI = 3.141592653589793_wp

    ! --- Power Transmission System (PTS) Constants (Kikuchi Table 7) ---
    REAL(wp), PARAMETER :: C_ON_SUBS  = 25000.0_wp       ! Onshore sub (GBP/MW)
    REAL(wp), PARAMETER :: C_OC_UNIT  = 731698.0_wp      ! Onshore cable (GBP/km)
    REAL(wp), PARAMETER :: L_OC       = 1.0_wp           ! Onshore cable length (km)
    REAL(wp), PARAMETER :: C_OFF_SUBS = 58445000.0_wp    ! Offshore sub (GBP/sub)
    REAL(wp), PARAMETER :: C_EC_UNIT  = 731698.0_wp      ! Export cable (GBP/km)
    REAL(wp), PARAMETER :: C_AC_UNIT  = 220755.0_wp      ! Array cable (GBP/km)
    REAL(wp), PARAMETER :: V_EC       = 132.0_wp         ! Export voltage (kV)
    REAL(wp), PARAMETER :: A_EC1 = 1.18_wp
    REAL(wp), PARAMETER :: A_EC2 = 0.92_wp
    REAL(wp), PARAMETER :: A_EC3 = 26.48_wp
    REAL(wp), PARAMETER :: KAPPA = 1.2_wp
    REAL(wp), PARAMETER :: BETA1 = 5.0_wp
    REAL(wp), PARAMETER :: BETA3 = 7.0_wp
    REAL(wp), PARAMETER :: H_P   = 20.0_wp               ! Tower bottom to sea surface (m)

    ! --- Installation and Commissioning (I&C) Constants (Kikuchi Table 8) ---
    REAL(wp), PARAMETER :: C_PORT     = 146000.0_wp      ! Port cost (GBP/turbine)
    REAL(wp), PARAMETER :: C_OTHERS   = 2120000.0_wp     ! Insurance/mgmt (GBP/turbine)
    REAL(wp), PARAMETER :: C_V_INST_SS = 315603.0_wp     ! SS Vessel day rate (GBP/day)
    REAL(wp), PARAMETER :: C_V_INST_WT = 315603.0_wp     ! WT Vessel day rate (GBP/day)
    REAL(wp), PARAMETER :: C_V_FUEL_SS = 333.33_wp       ! SS Fuel cost (GBP/km)
    REAL(wp), PARAMETER :: C_V_FUEL_WT = 333.33_wp       ! WT Fuel cost (GBP/km)
    REAL(wp), PARAMETER :: T_INST_SS  = 3.35_wp          ! Days to install 1 Monopile
    REAL(wp), PARAMETER :: T_INST_WT  = 3.60_wp          ! Days to install 1 Turbine
    REAL(wp), PARAMETER :: V_KNOTS    = 11.0_wp          ! Vessel speed (knots)
    REAL(wp), PARAMETER :: KM_PER_KNOT = 1.852_wp        ! Conversion factor
    REAL(wp), PARAMETER :: N_TRANSPORT = 4.0_wp          ! Components per trip
    
    ! Cable & Substation Installation
    REAL(wp), PARAMETER :: C_INST_AC       = 662266.0_wp ! Array cable install (GBP/km)
    REAL(wp), PARAMETER :: C_INST_EC       = 975393.0_wp ! Export cable install (GBP/km)
    REAL(wp), PARAMETER :: C_INST_OFF_SUBS = 11689000.0_wp ! Offshore sub install
    REAL(wp), PARAMETER :: C_INST_ON_SUBS  = 25000.0_wp  ! Onshore sub install (GBP/MW)

CONTAINS

    ! ==================================================================
    ! SUBROUTINE: evaluate_financial_cost
    ! Master routing to calculate total farm cost
    ! ==================================================================
    SUBROUTINE evaluate_financial_cost(ind, site, turbines, config)
        TYPE(Individual),  INTENT(INOUT) :: ind
        TYPE(SiteData),    INTENT(IN)    :: site
        TYPE(TurbineSpec), INTENT(IN)    :: turbines(:)
        Type(ConfigData),  Intent(In)    :: config
        
        REAL(wp) :: dcpa_cost, l_ac, l_ec
        REAL(wp) :: cable_cost, inc_cost
        INTEGER  :: n_turb, n_ec, n_subs
        
        ! Count active turbines
        n_turb = COUNT(ind%chromosome > 1)
        
        ! ! Penalty for empty layouts >>> Already done in NSGA-II evaluation loop
        ! IF (n_turb == 0) THEN
        !     ind%obj_vals(1) = 1.0E9_wp 
        !     RETURN
        ! END IF
        
        ! 1. Production & Acquisition Cost
        dcpa_cost = calc_pa_cost(ind, site, turbines)
        
        ! 2. Power Transmission Cost (Now also outputs lengths for step 3)
        CALL calc_cable_cost(ind, site, turbines, cable_cost, l_ac, l_ec, n_ec, n_subs)
        
        ! 3. Installation & Commissioning Cost
        inc_cost = calc_install_cost(ind, site, turbines, config, l_ac, l_ec, n_ec, n_subs)
        
        ! TOTAL CAPEX
        ind%raw_cost = dcpa_cost + cable_cost + inc_cost
        
    END SUBROUTINE evaluate_financial_cost

    ! ==================================================================
    ! FUNCTION: calc_pa_cost (Modernized Kikuchi Model)
    ! ==================================================================
    FUNCTION calc_pa_cost(ind, site, turbines) RESULT(total_dc_pa_cost)
        TYPE(Individual),  INTENT(IN) :: ind
        TYPE(SiteData),    INTENT(IN) :: site
        TYPE(TurbineSpec), INTENT(IN) :: turbines(:)
        REAL(wp) :: total_dc_pa_cost
        
        INTEGER  :: i, t_type
        REAL(wp) :: p_wt, depth, unit_cost_mw
        REAL(wp) :: cost_wt_single, cost_ss_single
        REAL(wp) :: d_ss, t_ss, l_ss, w_ss
        real(wp) :: total_nominal_power, fdc, sc

        total_dc_pa_cost = 0.0_wp
        total_nominal_power = 0.0_wp

        DO i = 1, site%n_nodes
            t_type = ind%chromosome(i)
            
            ! If there is a turbine at this node (t_type > 1 is valid turbine)
            IF (t_type > 1) THEN
                
                ! Extract properties
                p_wt  = turbines(t_type)%rated_power
                depth = max(0.0_wp, -site%z_coord(i)) ! Ensure non-negative depth
                total_nominal_power = total_nominal_power + p_wt
                ! ------------------------------------------------------
                ! A. Wind Turbine Cost (C_WT)
                ! ------------------------------------------------------
                IF (p_wt <= 6.0_wp) THEN
                    unit_cost_mw = (CWT1 * p_wt) + CWT2
                ELSE IF (p_wt < 7.0_wp) THEN
                    unit_cost_mw = (CWT3 * p_wt) + CWT4
                ELSE
                    unit_cost_mw = CWT5
                END IF
                cost_wt_single = unit_cost_mw * p_wt

                ! ------------------------------------------------------
                ! B. Support Structure Cost (C_SS)
                ! ------------------------------------------------------
                ! Monopile Dimensions
                d_ss = (0.0003_wp * (depth**2)) + (0.0627_wp * depth) + 3.9687_wp
                IF (d_ss < 4.0_wp) d_ss = 4.0_wp
                
                t_ss = (A_SS1 * depth) + A_SS2
                l_ss = (A_SS3 * depth) + A_SS4
                
                ! Monopile Mass (W_ss)
                w_ss = PI * d_ss * t_ss * l_ss * RHO_STEEL
                
                ! Support Structure Cost
                cost_ss_single = w_ss * (C_SS_STEEL + C_SS_PROD)

                ! ------------------------------------------------------
                ! C. Accumulate Total
                ! ------------------------------------------------------
                total_dc_pa_cost = total_dc_pa_cost + cost_wt_single + cost_ss_single

            END IF
        END DO
        ! fixed development cost
        if (total_nominal_power <= 300.0_wp) then
            fdc = 3684373.0_wp                  ! GPB
        ELSE
            fdc = 23378000.0_wp                 ! GBP
        END IF
        ! survey cost
        sc = total_nominal_power * 97792.0_wp   ! GBP
        
        total_dc_pa_cost = total_dc_pa_cost + fdc + sc
    END FUNCTION calc_pa_cost

    ! ==================================================================
    ! SUBROUTINE: calc_cable_cost (Kikuchi Power Transmission System)
    ! ==================================================================
    SUBROUTINE calc_cable_cost(ind, site, turbines, total_pts_cost, &
                               l_ac_out, l_ec_out, n_ec_out, n_off_subs_out)
                               
        TYPE(Individual),  INTENT(IN)  :: ind
        TYPE(SiteData),    INTENT(IN)  :: site
        TYPE(TurbineSpec), INTENT(IN)  :: turbines(:)
        
        ! Explicit outputs for downstream calculations (Installation phase)
        REAL(wp), INTENT(OUT) :: total_pts_cost
        REAL(wp), INTENT(OUT) :: l_ac_out, l_ec_out
        INTEGER,  INTENT(OUT) :: n_ec_out, n_off_subs_out

        ! Local variables
        INTEGER  :: i, t_type, n_turb
        REAL(wp) :: p_wt, depth, d_rotor
        REAL(wp) :: cap, avg_p_wt, avg_depth, avg_d_rotor
        REAL(wp) :: v_ac, delta_l_ec, delta_l_pts, x_dist, l_ac_m
        INTEGER  :: n_ac
        
        REAL(wp) :: cost_on_subs, cost_oc, cost_off_subs, cost_ec, cost_ac
        
        cap = 0.0_wp
        avg_depth = 0.0_wp
        avg_d_rotor = 0.0_wp
        n_turb = 0
        
        ! 1. Gather farm-level averages and totals
        DO i = 1, site%n_nodes
            t_type = ind%chromosome(i)
            IF (t_type > 1) THEN
                p_wt = turbines(t_type)%rated_power
                d_rotor = turbines(t_type)%rotor_diameter
                depth = MAX(0.0_wp, -site%z_coord(i))
                
                cap = cap + p_wt
                avg_depth = avg_depth + depth
                avg_d_rotor = avg_d_rotor + d_rotor
                n_turb = n_turb + 1
            END IF
        END DO
        
        ! ! Safety catch for empty farm >>> Already done in NSGA-II evaluation loop
        ! IF (n_turb == 0) THEN
        !     total_pts_cost = 0.0_wp
        !     RETURN
        ! END IF
        
        avg_p_wt = cap / REAL(n_turb, wp)
        avg_depth = avg_depth / REAL(n_turb, wp)
        avg_d_rotor = avg_d_rotor / REAL(n_turb, wp)
        
        ! 2. Determine Array Cable Voltage (V_AC)
        IF (avg_p_wt <= 2.0_wp) THEN
            v_ac = 22.0_wp
        ELSE IF (avg_p_wt <= 9.0_wp) THEN
            v_ac = 33.0_wp
        ELSE
            v_ac = 66.0_wp
        END IF
        
        ! 3. Determine Number of Cable Strings
        n_ac = CEILING(cap / v_ac)
        n_ec_out = CEILING(cap / (1.2_wp * V_EC))
        
        ! 4. Calculate Export Cable Length (l_EC)
        delta_l_ec = ABS(site%d_landfall - site%d_shore)
        IF (delta_l_ec < 5.0_wp) THEN
            l_ec_out = (A_EC1 * site%d_shore) + A_EC2
        ELSE
            l_ec_out = (A_EC1 * site%d_shore) + A_EC3
        END IF
        
        ! 5. Determine Offshore Substation Decision
        delta_l_pts = l_ec_out * REAL(n_ac - n_ec_out, wp)
        
        IF (delta_l_pts > 55.0_wp) THEN
            n_off_subs_out = CEILING(cap / 500.0_wp)
        ELSE
            n_off_subs_out = 0
        END IF
        
        ! 6. Calculate Component Costs
        
        ! A. Onshore Substation & Onshore Cable
        cost_on_subs = C_ON_SUBS * cap
        cost_oc      = L_OC * C_OC_UNIT
        
        ! B. Offshore Substation
        cost_off_subs = REAL(n_off_subs_out, wp) * C_OFF_SUBS
        
        ! C. Array and Export Cables
        IF (n_off_subs_out == 0) THEN
            ! Radial topology without substation
            l_ac_m = (BETA1 * avg_d_rotor * REAL(n_turb - n_ac, wp)) + &
                     ((avg_depth + H_P) * REAL(2*n_turb - n_ac, wp))
            cost_ec = l_ec_out * C_AC_UNIT * REAL(n_ac, wp)
        ELSE
            ! Ring topology with substation
            x_dist = 1.5_wp * BETA3 * avg_d_rotor
            l_ac_m = KAPPA * ((BETA3 * avg_d_rotor * (REAL(n_turb, wp) - 0.5_wp * REAL(n_ac, wp))) + &
                     (x_dist * REAL(n_ac, wp)) + &
                     ((avg_depth + H_P) * REAL(2*n_turb, wp)))
            cost_ec = l_ec_out * C_EC_UNIT * REAL(n_ec_out, wp)
        END IF
        
        
        ! Set the array cable output variable (converted to km)
        l_ac_out = l_ac_m / 1000.0_wp
        cost_ac = l_ac_out * C_AC_UNIT

        ! 7. Total Power Transmission System Cost
        total_pts_cost = cost_on_subs + cost_oc + cost_off_subs + cost_ac + cost_ec
        
    END SUBROUTINE calc_cable_cost

    ! ==================================================================
    ! FUNCTION: calc_install_cost (Kikuchi Installation & Commissioning)
    ! ==================================================================
    FUNCTION calc_install_cost(ind, site, turbines, config, l_ac, l_ec, n_ec, n_off_subs) RESULT(total_inc_cost)
        TYPE(Individual),  INTENT(IN) :: ind
        TYPE(SiteData),    INTENT(IN) :: site
        TYPE(TurbineSpec), INTENT(IN) :: turbines(:)
        type(ConfigData),  Intent(IN) :: config
        REAL(wp), INTENT(IN) :: l_ac, l_ec       ! Cable lengths in km
        INTEGER,  INTENT(IN) :: n_ec, n_off_subs ! Number of export cables and substations
        
        REAL(wp) :: total_inc_cost
        
        INTEGER  :: i, t_type, n_turb
        REAL(wp) :: p_wt, cap, v_kmh, a_vessel_wt, a_vessel_ss
        REAL(wp) :: trips, transit_time_days, transit_dist_km
        REAL(wp) :: cost_port, cost_others, cost_cable_subs
        REAL(wp) :: c_mob_wt, c_fuel_wt, c_inst_wt
        REAL(wp) :: c_mob_ss, c_fuel_ss, c_inst_ss
        
        cap = 0.0_wp
        n_turb = COUNT(ind%chromosome > 1)
        IF (n_turb == 0) THEN
            total_inc_cost = 0.0_wp
            RETURN
        END IF

        ! 1. Calculate Vessel Speed in km/h
        v_kmh = V_KNOTS * KM_PER_KNOT

        ! 2. Initialize accumulators for the loop
        c_inst_wt = 0.0_wp; c_fuel_wt = 0.0_wp; c_mob_wt = 0.0_wp
        c_inst_ss = 0.0_wp; c_fuel_ss = 0.0_wp; c_mob_ss = 0.0_wp

        ! 3. Loop through turbines to calculate heterogenous vessel sizes & times
        DO i = 1, site%n_nodes
            t_type = ind%chromosome(i)
            IF (t_type > 1) THEN
                p_wt = turbines(t_type)%rated_power
                cap = cap + p_wt
                
                ! A. Determine Vessel Size Multipliers based on Turbine MW
                ! (From Kikuchi Section 3.2.3 and Equations 9 & 10)
                IF (p_wt <= 3.6_wp) THEN
                    a_vessel_wt = 0.91_wp  ! Expected value from logit
                    a_vessel_ss = 0.97_wp
                ELSE IF (p_wt <= 10.0_wp) THEN
                    a_vessel_wt = 1.0_wp
                    a_vessel_ss = 1.0_wp
                ELSE
                    a_vessel_wt = 1.49_wp
                    a_vessel_ss = 1.38_wp
                END IF
                
                ! B. Calculate Trips for this specific turbine (fractional for smooth GA)
                trips = 1.0_wp / N_TRANSPORT
                transit_dist_km = 2.0_wp * trips * site%d_port
                transit_time_days = transit_dist_km / (24.0_wp * v_kmh)
                
                ! C. Accumulate Turbine (WT) Vessel Costs
                c_inst_wt = c_inst_wt + (a_vessel_wt * C_V_INST_WT * &
                            (transit_time_days + (T_INST_WT / config%workability)))
                c_fuel_wt = c_fuel_wt + (a_vessel_wt * C_V_FUEL_WT * transit_dist_km)
                
                ! D. Accumulate Substructure (SS) Vessel Costs
                c_inst_ss = c_inst_ss + (a_vessel_ss * C_V_INST_SS * &
                            (transit_time_days + (T_INST_SS / config%workability)))
                c_fuel_ss = c_fuel_ss + (a_vessel_ss * C_V_FUEL_SS * transit_dist_km)
            END IF
        END DO
        
        ! Mobilization is 1% of the total pure installation cost
        c_mob_wt = 0.01_wp * c_inst_wt
        c_mob_ss = 0.01_wp * c_inst_ss
        
        ! 4. Calculate Static Fixed Costs
        cost_port   = C_PORT * REAL(n_turb, wp)
        cost_others = C_OTHERS * REAL(n_turb, wp)
        
        ! 5. Calculate Cable & Substation Installation
        ! Note: Export cable install cost is multiplied by number of export cables (n_ec)
        cost_cable_subs = (l_ac * C_INST_AC) + &
                          (l_ec * REAL(n_ec, wp) * C_INST_EC) + &
                          (REAL(n_off_subs, wp) * C_INST_OFF_SUBS) + &
                          (cap * C_INST_ON_SUBS)
                          
        ! 6. Final Summation
        total_inc_cost = cost_port + cost_others + cost_cable_subs + &
                         c_inst_wt + c_fuel_wt + c_mob_wt + &
                         c_inst_ss + c_fuel_ss + c_mob_ss

    END FUNCTION calc_install_cost

END MODULE costs

MODULE physics

    USE precision, ONLY: wp
    USE types,     ONLY: SiteData, TurbineSpec, Individual, ConfigData
    
    IMPLICIT NONE
    PRIVATE

    ! Expose ONLY the top-level evaluation routines
    PUBLIC :: evaluate_physics
    PUBLIC :: calculate_3d_wind_field

    ! ==================================================================
    ! TEMPORARY HARDCODED FATIGUE & ENVIRONMENTAL PARAMETERS (Yang 2025)
    ! ==================================================================
    REAL(wp), PARAMETER :: I_ambient = 0.08_wp       ! Ambient Turbulence Intensity (8%)
    REAL(wp), PARAMETER :: g_v       = 3.7_wp        ! Gust factor (3-s gust)
    REAL(wp), PARAMETER :: rho       = 1.225_wp      ! Air density (kg/m^3)
    REAL(wp), PARAMETER :: pi        = 3.141592653589793_wp
    
    ! Structural (Tower Root Approximation for typical 2MW-5MW)
    REAL(wp), PARAMETER :: r_pile    = 2.0_wp        ! Tower root radius (m)
    REAL(wp), PARAMETER :: t_tower   = 0.03_wp       ! Tower root thickness (m)
    REAL(wp), PARAMETER :: I_z       = pi * &
                            (r_pile**3) * t_tower    ! Area moment of inertia (m^4) ~ pi * r^3 * t
    
    ! Material Properties (Typical Offshore Steel in MPa)
    REAL(wp), PARAMETER :: sigma_y   = 345.0_wp      ! Yield strength (MPa)
    REAL(wp), PARAMETER :: sigma_b   = 450.0_wp      ! Ultimate tensile strength (MPa)
    
    ! S-N Curve Constants (DNV Standards for Tubular Joints)
    REAL(wp), PARAMETER :: t_ref     = 0.032_wp      ! Reference thickness (m)
    REAL(wp), PARAMETER :: k_fatigue = 0.10_wp       ! Thickness exponent

    ! Turbine Operational Data
    REAL(wp), PARAMETER :: rpm_avg   = 12.0_wp       ! Average Rotor RPM
    REAL(wp), PARAMETER :: cycles_per_hr = rpm_avg * 60.0_wp ! cycles per hour (720)

CONTAINS

    ! ==================================================================
    ! SUBROUTINE: evaluate_physics (Wake + Power + Fatigue)
    ! ==================================================================
    SUBROUTINE evaluate_physics(ind, site, turbines, config)
        TYPE(Individual),  INTENT(INOUT) :: ind
        TYPE(SiteData),    INTENT(IN)    :: site
        TYPE(TurbineSpec), INTENT(IN)    :: turbines(:)
        TYPE(ConfigData),  INTENT(IN)    :: config

        INTEGER :: n_turb, i, m, t_step, t_type, n_idx, k_iter
        REAL(wp) :: total_aep, tep_farm, v_local, i_local, cp_val, area, m_ct
        REAL(wp) :: F_mean, F_peak, sig_mean, sig_max, sig_a, sig_m, sig_e
        REAL(wp) :: N_cycles, log_N, thickness_corr

        ! --- SPARSE ARRAYS ---
        INTEGER, ALLOCATABLE  :: node_idx(:), type_turb(:), h_idx(:)
        REAL(wp), ALLOCATABLE :: ws_new(:), ws_old(:), ti_new(:)
        REAL(wp), ALLOCATABLE :: wake_deficit_u(:), single_deficit_u(:)
        REAL(wp), ALLOCATABLE :: wake_added_i(:), single_added_i(:)
        REAL(wp), ALLOCATABLE :: cum_damage(:) ! Cumulative Fatigue Damage
        
        n_turb = COUNT(ind%chromosome > 1)
        IF (n_turb == 0) RETURN

        ALLOCATE(node_idx(n_turb), type_turb(n_turb), h_idx(n_turb))
        ALLOCATE(ws_new(n_turb), ws_old(n_turb), ti_new(n_turb))
        ALLOCATE(wake_deficit_u(n_turb), single_deficit_u(n_turb))
        ALLOCATE(wake_added_i(n_turb), single_added_i(n_turb))
        ALLOCATE(cum_damage(n_turb))
        
        cum_damage = 0.0_wp

        ! Build lookup tables
        m = 1
        DO i = 1, site%n_nodes
            t_type = ind%chromosome(i)
            IF (t_type > 1) THEN
                node_idx(m) = i
                type_turb(m) = t_type
                h_idx(m) = turbines(t_type)%h_idx
                m = m + 1
            END IF
        END DO

        total_aep = 0.0_wp
        thickness_corr = k_fatigue * LOG10(t_tower / t_ref)

        ! --------------------------------------------------------------
        ! MAIN TIME-STEP LOOP (Hourly Data)
        ! --------------------------------------------------------------
        DO t_step = 1, site%nsteps
            
            ! Initialize local wind speeds and ambient TI
            DO m = 1, n_turb
                n_idx = node_idx(m)
                ws_new(m) = site%ws0_ts(n_idx, h_idx(m), t_step)
                ti_new(m) = I_ambient 
            END DO
            
            ! ----------------------------------------------------------
            ! ALL-TO-ALL ITERATIVE WAKE SOLVER (Velocity & Turbulence)
            ! ----------------------------------------------------------
            DO k_iter = 1, config%max_iter 
                ws_old = ws_new 
                wake_deficit_u = 0.0_wp
                wake_added_i   = 0.0_wp
                
                ! Calculate wakes produced by active turbines
                DO m = 1, n_turb
                    t_type = type_turb(m)
                    n_idx  = node_idx(m)
                    v_local = ws_new(m)
                    
                    m_ct = get_coeff(v_local, turbines(t_type)%v_ref, &
                                     turbines(t_type)%ct_ref, turbines(t_type)%n_points)
                    
                    CALL analytical_wake_sparse(m, n_idx, turbines(t_type), m_ct, site, turbines, &
                                                n_turb, node_idx, type_turb, t_step, &
                                                single_deficit_u, single_added_i)
                    
                    ! Superposition: Sum of Squares for Velocity, TKE for Turbulence
                    wake_deficit_u = wake_deficit_u + (single_deficit_u**2)
                    wake_added_i   = wake_added_i + (single_added_i**2)
                END DO

                ! Apply aggregated wake to local conditions
                DO m = 1, n_turb
                    IF (SQRT(wake_deficit_u(m)) < 1.0_wp) THEN
                        n_idx = node_idx(m)          
                        ws_new(m) = site%ws0_ts(n_idx, h_idx(m), t_step) * (1.0_wp - SQRT(wake_deficit_u(m)))
                        ti_new(m) = SQRT(I_ambient**2 + wake_added_i(m))
                    ELSE
                        ws_new(m) = 0.0_wp
                        ti_new(m) = I_ambient
                    END IF
                END DO

                ! Convergence Check
                IF (MAXVAL(ABS(ws_new - ws_old)) < 1.0E-4_wp) EXIT 
            END DO 
            
            ! ----------------------------------------------------------
            ! Calculate POWER & FATIGUE using converged local speeds
            ! ----------------------------------------------------------
            tep_farm = 0.0_wp
            DO m = 1, n_turb
                t_type = type_turb(m)
                v_local = ws_new(m)
                i_local = ti_new(m)
                
                ! --- 1. POWER ---
                cp_val = get_coeff(v_local, turbines(t_type)%v_ref, &
                                   turbines(t_type)%cp_ref, turbines(t_type)%n_points)
                area = pi * (turbines(t_type)%rotor_diameter / 2.0_wp)**2
                tep_farm = tep_farm + (0.5_wp * rho * area * (v_local**3) * cp_val)
                
                ! --- 2. FATIGUE ---
                ! Only calculate operational fatigue if turbine is spinning
                IF (v_local >= turbines(t_type)%v_ref(1) .AND. cp_val > 0.0_wp) THEN
                    m_ct = get_coeff(v_local, turbines(t_type)%v_ref, &
                                     turbines(t_type)%ct_ref, turbines(t_type)%n_points)
                                     
                    ! Thrust forces (Newtons)
                    F_mean = 0.5_wp * rho * area * m_ct * (v_local**2)
                    F_peak = 0.5_wp * rho * area * m_ct * ((v_local * (1.0_wp + g_v * i_local))**2)
                    
                    ! Stresses at tower root (Convert Pascals to MPa for DNV curve)
                    sig_mean = (F_mean * turbines(t_type)%hub_height * r_pile) / I_z / 1.0E6_wp
                    sig_max  = (F_peak * turbines(t_type)%hub_height * r_pile) / I_z / 1.0E6_wp
                    sig_a    = sig_max - sig_mean
                    
                    ! Modified average stress (Goodman Correction - Eq 8)
                    IF ((sig_mean + sig_a) < sigma_y) THEN
                        sig_m = sig_mean
                    ELSE IF ((sig_mean + sig_a) >= sigma_y .AND. sig_mean < sigma_y) THEN
                        sig_m = sigma_y - sig_a
                    ELSE
                        sig_m = 0.0_wp
                    END IF
                    
                    ! Equivalent stress amplitude (Eq 7)
                    sig_e = sig_a / (1.0_wp - (sig_m / sigma_b))
                    
                    ! S-N Curve Cycles to Failure (Eq 9 & 10)
                    ! Check low-cycle vs high-cycle regime
                    ! Assume High-cycle first (m=5) to check N > 10^7
                    log_N = 16.081_wp - 5.0_wp * LOG10(sig_e) - 5.0_wp * thickness_corr
                    N_cycles = 10.0_wp**log_N
                    
                    IF (N_cycles <= 1.0E7_wp) THEN
                        ! Recalculate with Low-cycle curve (m=3)
                        log_N = 12.449_wp - 3.0_wp * LOG10(sig_e) - 3.0_wp * thickness_corr
                        N_cycles = 10.0_wp**log_N
                    END IF
                    
                    ! Accumulate Fractional Damage via Miner's Rule
                    cum_damage(m) = cum_damage(m) + (cycles_per_hr / N_cycles)
                END IF
            END DO
            
            total_aep = total_aep + tep_farm
        END DO

        ! Post-process AEP
        total_aep = total_aep / REAL(site%nsteps, wp) 
        total_aep = total_aep * 8760.0_wp / 1.0E9_wp  
        ind%raw_aep = total_aep

        ind%raw_fatigue = MAXVAL(cum_damage) ! Maximum damage across turbines as farm-level fatigue metric

        ! Store Maximum Farm Damage as the secondary objective to minimize
        ! ind%obj_vals(2) = MAXVAL(cum_damage)

        DEALLOCATE(node_idx, type_turb, ws_new, ws_old, ti_new)
        DEALLOCATE(wake_deficit_u, single_deficit_u, wake_added_i, single_added_i)
        DEALLOCATE(cum_damage)

    END SUBROUTINE evaluate_physics

    ! ==================================================================
    ! SUBROUTINE: analytical_wake_sparse (Calculates dU and dI)
    ! ==================================================================
    SUBROUTINE analytical_wake_sparse(m, n_idx, t_spec, m_ct1, site, turbines, &
                                      n_turb, node_idx, type_turb, t_step, deficit_u, added_i)
        TYPE(SiteData),    INTENT(IN)  :: site
        TYPE(TurbineSpec), INTENT(IN)  :: turbines(:)
        TYPE(TurbineSpec), INTENT(IN)  :: t_spec
        INTEGER,           INTENT(IN)  :: m, n_idx, n_turb, t_step
        INTEGER,           INTENT(IN)  :: node_idx(:), type_turb(:)
        REAL(wp),          INTENT(IN)  :: m_ct1
        REAL(wp),          INTENT(OUT) :: deficit_u(:), added_i(:) 
        
        REAL(wp), PARAMETER :: k_star = 0.0324_wp 
        
        REAL(wp) :: beta, hubX, hubY, theta, d_wake, h_wake
        REAL(wp) :: dx, dy, x_rot, y_rot, x_rel
        REAL(wp) :: radial_dist, sigma_d0, a1, b1, c1, c2, z_coord
        INTEGER  :: i, j_node, j_type
        REAL(wp) :: m_ct
        
        deficit_u = 0.0_wp
        added_i   = 0.0_wp
        
        hubX   = site%x_coord(n_idx)
        hubY   = site%y_coord(n_idx)
        theta  = site%wd0_ts(n_idx, t_step)
        d_wake = t_spec%rotor_diameter
        h_wake = t_spec%hub_height
        m_ct   = MAX(0.0001_wp, MIN(m_ct1, 0.9999_wp))
        beta   = 0.5_wp * ((1.0_wp + SQRT(1.0_wp - m_ct)) / SQRT(1.0_wp - m_ct))

        DO i = 1, n_turb
            IF (i == m) CYCLE
            j_node = node_idx(i)
            
            dx = site%x_coord(j_node) - hubX
            dy = site%y_coord(j_node) - hubY
            x_rot =  dx * COS(theta) + dy * SIN(theta)
            y_rot = -dx * SIN(theta) + dy * COS(theta)
            
            radial_dist = ABS(y_rot)
            x_rel = MAX(x_rot, 0.0_wp)
            
            IF (x_rel > 1.0_wp .AND. radial_dist < (3.0_wp * d_wake)) THEN
                
                ! Velocity Deficit (Bastankhah Gaussian)
                sigma_d0 = (k_star * x_rel / d_wake) + (0.2_wp * SQRT(beta))
                a1 = m_ct / (8.0_wp * (sigma_d0 ** 2))
                IF (a1 >= 1.0_wp) a1 = 0.999_wp
                
                b1 = -1.0_wp / (2.0_wp * (sigma_d0 ** 2))
                c2 = (radial_dist / d_wake) ** 2
                
                j_type  = type_turb(i)
                z_coord = turbines(j_type)%hub_height
                c1 = ((z_coord - h_wake) / d_wake) ** 2
                
                deficit_u(i) = (1.0_wp - SQRT(1.0_wp - a1)) * EXP(b1 * (c1 + c2))
                
                ! Turbulence Addition (Generic Empirical Stand-in for Ishihara)
                ! Form: dI = K * a^x * I_0^y * (x/D)^z
                added_i(i) = 0.73_wp * (1.0_wp - SQRT(1.0_wp - m_ct))**0.8325_wp * &
                             I_ambient**0.0325_wp * (x_rel / d_wake)**(-0.32_wp)
            END IF
        END DO
    END SUBROUTINE analytical_wake_sparse

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

END MODULE physics

! MODULE power

!     USE precision, ONLY: wp
!     USE types,     ONLY: SiteData, TurbineSpec, Individual, ConfigData
    
!     IMPLICIT NONE
!     PRIVATE

!     ! Expose ONLY the top-level evaluation routine
!     PUBLIC :: evaluate_aep
!     public :: calculate_3d_wind_field

! CONTAINS

!     ! ==================================================================
!     ! SUBROUTINE: evaluate_aep (Optimized Sparse Matrix Approach)
!     ! ==================================================================
!     SUBROUTINE evaluate_aep(ind, site, turbines, config)
!         TYPE(Individual),  INTENT(INOUT) :: ind
!         TYPE(SiteData),    INTENT(IN)    :: site
!         TYPE(TurbineSpec), INTENT(IN)    :: turbines(:)
!         TYPE(ConfigData),  INTENT(IN)    :: config

!         INTEGER :: n_turb, i, m, t_step, t_type, n_idx, k_iter
!         REAL(wp) :: total_aep, tep_farm, v_local, cp_val, area, m_ct
!         REAL(wp), PARAMETER :: rho = 1.225_wp, pi = 3.141592653589793_wp

!         ! --- SPARSE ARRAYS ---
!         INTEGER, ALLOCATABLE  :: node_idx(:), type_turb(:), h_idx(:)
!         REAL(wp), ALLOCATABLE :: ws_new(:), ws_old(:)
!         REAL(wp), ALLOCATABLE :: wake_deficit(:), single_deficit(:)
        
!         ! 1. Extract Active Turbines to Sparse Arrays (The Performance Fix)
!         n_turb = COUNT(ind%chromosome > 1)
!         ! IF (n_turb == 0) THEN
!         !     ind%obj_vals(2) = 0.0_wp  
!         !     RETURN
!         ! END IF

!         ALLOCATE(node_idx(n_turb), type_turb(n_turb), h_idx(n_turb))
!         ALLOCATE(ws_new(n_turb), ws_old(n_turb))
!         ALLOCATE(wake_deficit(n_turb), single_deficit(n_turb))

!         ! Build the lookup tables
!         m = 1
!         DO i = 1, site%n_nodes
!             t_type = ind%chromosome(i)
!             IF (t_type > 1) THEN
!                 node_idx(m) = i
!                 type_turb(m) = ind%chromosome(i)
!                 h_idx(m)     = turbines(t_type)%h_idx
!                 m = m + 1
!             END IF
!         END DO

!         total_aep = 0.0_wp

!         ! --------------------------------------------------------------
!         ! MAIN TIME-STEP LOOP
!         ! --------------------------------------------------------------
!         DO t_step = 1, site%nsteps
            
!             ! Initialize local wind speeds for the active turbines ONLY
!             DO m = 1, n_turb
!                 n_idx = node_idx(m)
!                 ws_new(m) = site%ws0_ts(n_idx, h_idx(m), t_step)
!             END DO
            
!             ! ----------------------------------------------------------
!             ! ALL-TO-ALL ITERATIVE SOLVER (Sparse Logic)
!             ! ----------------------------------------------------------
!             DO k_iter = 1, config%max_iter 
!                 ws_old = ws_new 
!                 wake_deficit = 0.0_wp
                
!                 ! Loop 1: Calculate wakes produced by active turbines
!                 DO m = 1, n_turb
!                     t_type = type_turb(m)
!                     n_idx  = node_idx(m)
!                     v_local = ws_new(m)
                    
!                     m_ct = get_coeff(v_local, turbines(t_type)%v_ref, &
!                                      turbines(t_type)%ct_ref, turbines(t_type)%n_points)
                    
!                     ! ONLY calculate deficit AT the other turbine locations!
!                     CALL bastankhah_wake_sparse(m, n_idx, turbines(t_type), m_ct, site, turbines, &
!                                                 n_turb, node_idx, type_turb, t_step, single_deficit)
                    
!                     wake_deficit = wake_deficit + (single_deficit**2)
!                 END DO

!                 ! Loop 2: Apply the total aggregated wake
!                 DO m = 1, n_turb
!                     IF (SQRT(wake_deficit(m)) < 1.0_wp) THEN
!                         n_idx = node_idx(m)          
!                         ! Multiply original free-stream by the wake fraction
!                         ws_new(m) = site%ws0_ts(n_idx, h_idx(m), t_step) * (1.0_wp - SQRT(wake_deficit(m)))
!                     ELSE
!                         ws_new(m) = 0.0_wp
!                     END IF
!                 END DO

!                 ! Convergence Check (comparing just the n_turb values)
!                 IF (MAXVAL(ABS(ws_new - ws_old)) < 1.0E-4_wp) EXIT 
!             END DO 
            
!             ! ----------------------------------------------------------
!             ! Calculate power using the FINAL converged local speeds
!             ! ----------------------------------------------------------
!             tep_farm = 0.0_wp
!             DO m = 1, n_turb
!                 t_type = type_turb(m)
!                 v_local = ws_new(m)
                
!                 cp_val = get_coeff(v_local, turbines(t_type)%v_ref, &
!                                    turbines(t_type)%cp_ref, turbines(t_type)%n_points)
                
!                 area = pi * (turbines(t_type)%rotor_diameter / 2.0_wp)**2
!                 tep_farm = tep_farm + (0.5_wp * rho * area * (v_local**3) * cp_val)
!             END DO
            
!             total_aep = total_aep + tep_farm
!         END DO

!         total_aep = total_aep / REAL(site%nsteps, wp) ! Average Power (Watts)
!         total_aep = total_aep * 8760.0_wp / 1.0E9_wp  ! Annual Energy Production (GWh / Year)
!         ! ind%obj_vals(1) = ind%obj_vals(1) / (total_aep * config%farmlifetime)
!         ! ind%obj_vals(2) = -total_aep * config%farmlifetime
!         ! ! --- NEW: Store purely as Raw AEP (Lifetime GWh) ---
!         ! ind%raw_aep = total_aep * config%farmlifetime
!         ind%raw_aep = total_aep

!         DEALLOCATE(node_idx, type_turb, ws_new, ws_old, wake_deficit, single_deficit)

!     END SUBROUTINE evaluate_aep

!     ! ==================================================================
!     ! SUBROUTINE: bastankhah_wake_sparse
!     ! (Strict mathematical port of original F77 logic)
!     ! ==================================================================
!     SUBROUTINE bastankhah_wake_sparse(m, n_idx, t_spec, m_ct1, site, turbines, &
!                                       n_turb, node_idx, type_turb, t_step, deficit)
!         TYPE(SiteData),    INTENT(IN)  :: site
!         TYPE(TurbineSpec), INTENT(IN)  :: turbines(:)
!         TYPE(TurbineSpec), INTENT(IN)  :: t_spec
!         INTEGER,           INTENT(IN)  :: m, n_idx, n_turb, t_step
!         INTEGER,           INTENT(IN)  :: node_idx(:), type_turb(:)
!         REAL(wp),          INTENT(IN)  :: m_ct1
!         REAL(wp),          INTENT(OUT) :: deficit(:) ! Now a 1D array of size n_turb
        
!         REAL(wp), PARAMETER :: k_star = 0.0324_wp 
        
!         REAL(wp) :: beta, hubX, hubY, theta, d_wake, h_wake
!         REAL(wp) :: dx, dy, x_rot, y_rot, x_rel
!         REAL(wp) :: radial_dist, sigma_d0, a1, b1, c1, c2, z_coord
!         INTEGER  :: i, j_node, j_type
!         real(wp) :: m_ct
        
!         ! 1. Initialize output deficit array to zero
!         deficit = 0.0_wp
        
!         ! 2. Get properties of the wake-producing turbine (m)
!         hubX   = site%x_coord(n_idx)
!         hubY   = site%y_coord(n_idx)
!         theta  = site%wd0_ts(n_idx, t_step)
!         d_wake = t_spec%rotor_diameter
!         h_wake = t_spec%hub_height
!         m_ct = MAX(0.0001_wp, MIN(m_ct1, 0.9999_wp))
!         ! 3. Calculate beta
!         ! (Using MAX to prevent NaN if m_ct somehow hits 1.0)
!         beta = 0.5_wp * ((1.0_wp + SQRT(1.0_wp - m_ct)) / SQRT(1.0_wp - m_ct))
                                   

!         ! 4. Loop through ONLY the downstream active turbines
!         DO i = 1, n_turb
!             ! A turbine cannot wake itself
!             IF (i == m) CYCLE
            
!             j_node = node_idx(i)
            
!             ! 5. Calculate rotated coordinates (Exact match to old script)
!             dx = site%x_coord(j_node) - hubX
!             dy = site%y_coord(j_node) - hubY
!             x_rot =  dx * COS(theta) + dy * SIN(theta)
!             y_rot = -dx * SIN(theta) + dy * COS(theta)
            
!             radial_dist = ABS(y_rot)
!             x_rel = MAX(x_rot, 0.0_wp)
            
!             ! 6. Logic Gates: Downstream AND within 3 diameters
!             IF (x_rel > 1.0_wp .AND. radial_dist < (3.0_wp * d_wake)) THEN
                
!                 ! Calculate normalized wake diameter
!                 sigma_d0 = (k_star * x_rel / d_wake) + (0.2_wp * SQRT(beta))
                
!                 ! Pre-calculate Gaussian terms
!                 a1 = m_ct / (8.0_wp * (sigma_d0 ** 2))
                
!                 ! --- ANTI-NaN NEAR-WAKE CAP (Restored exactly) ---
!                 IF (a1 >= 1.0_wp) a1 = 0.999_wp
                
!                 b1 = -1.0_wp / (2.0_wp * (sigma_d0 ** 2))
!                 c2 = (radial_dist / d_wake) ** 2
                
!                 ! 7. Calculate height difference specifically for the target turbine
!                 j_type  = type_turb(i)
!                 z_coord = turbines(j_type)%hub_height
!                 c1 = ((z_coord - h_wake) / d_wake) ** 2
                
!                 ! 8. Apply exact deficit formula
!                 deficit(i) = (1.0_wp - SQRT(1.0_wp - a1)) * EXP(b1 * (c1 + c2))
                
!             END IF
!         END DO
!     END SUBROUTINE bastankhah_wake_sparse

    ! ! ==================================================================
    ! ! SUBROUTINE: bastankhah_wake_dense
    ! ! Calculates the wake deficit across ALL nodes and ALL height levels
    ! ! ==================================================================
    ! SUBROUTINE bastankhah_wake_dense(n_idx, t_spec, m_ct1, site, t_step, deficit)
    !     TYPE(SiteData),    INTENT(IN)  :: site
    !     TYPE(TurbineSpec), INTENT(IN)  :: t_spec
    !     INTEGER,           INTENT(IN)  :: n_idx, t_step
    !     REAL(wp),          INTENT(IN)  :: m_ct1
    !     REAL(wp),          INTENT(OUT) :: deficit(:,:) ! 2D: (n_nodes, n_hlevels)
        
    !     REAL(wp), PARAMETER :: k_star = 0.0324_wp
        
    !     REAL(wp) :: beta, hubX, hubY, theta, d_wake, h_wake
    !     REAL(wp) :: dx, dy, x_rot, y_rot, x_rel
    !     REAL(wp) :: radial_dist, sigma_d0, a1, b1, c1, c2, z_coord
    !     INTEGER  :: i, j

    !     real(wp) :: m_ct
        
    !     ! 1. Initialize output deficit array to zero
    !     deficit = 0.0_wp
        
    !     ! 2. Get properties of the wake-producing turbine
    !     hubX   = site%x_coord(n_idx)
    !     hubY   = site%y_coord(n_idx)
    !     theta  = site%wd0_ts(n_idx, t_step)
    !     d_wake = t_spec%rotor_diameter
    !     h_wake = t_spec%hub_height
    !     m_ct = MAX(0.0001_wp, MIN(m_ct1, 0.9999_wp))
    !     ! 3. Calculate beta
    !     beta = 0.5_wp * ((1.0_wp + SQRT(1.0_wp - m_ct)) / SQRT(1.0_wp - m_ct))

    !     ! 4. Loop through EVERY node in the grid
    !     DO i = 1, site%n_nodes
            
    !         ! 5. Calculate rotated coordinates
    !         dx = site%x_coord(i) - hubX
    !         dy = site%y_coord(i) - hubY
    !         x_rot =  dx * COS(theta) + dy * SIN(theta)
    !         y_rot = -dx * SIN(theta) + dy * COS(theta)
            
    !         radial_dist = ABS(y_rot)
    !         x_rel = MAX(x_rot, 0.0_wp)
            
    !         ! 6. Logic Gates: Downstream AND within 3 diameters
    !         IF (x_rel > 1.0_wp .AND. radial_dist < (3.0_wp * d_wake)) THEN
                
    !             sigma_d0 = (k_star * x_rel / d_wake) + (0.2_wp * SQRT(beta))
    !             a1 = m_ct / (8.0_wp * (sigma_d0 ** 2))
                
    !             IF (a1 >= 1.0_wp) a1 = 0.999_wp
                
    !             b1 = -1.0_wp / (2.0_wp * (sigma_d0 ** 2))
    !             c2 = (radial_dist / d_wake) ** 2
                
    !             ! 7. Calculate deficit for EVERY height level at this node
    !             DO j = 1, site%n_hlevel
    !                 z_coord = site%h_level(j)
    !                 c1 = ((z_coord - h_wake) / d_wake) ** 2
                    
    !                 deficit(i, j) = (1.0_wp - SQRT(1.0_wp - a1)) * EXP(b1 * (c1 + c2))
    !             END DO
    !         END IF
    !     END DO
    ! END SUBROUTINE bastankhah_wake_dense

!     ! ==================================================================
!     ! SUBROUTINE: calculate_3d_wind_field
!     ! Solves the full 3D wind field for visualization/post-processing
!     ! ==================================================================
!     SUBROUTINE calculate_3d_wind_field(ind, site, turbines, config, ws_out)
!         TYPE(Individual),  INTENT(IN)  :: ind
!         TYPE(SiteData),    INTENT(IN)  :: site
!         TYPE(TurbineSpec), INTENT(IN)  :: turbines(:)
!         TYPE(ConfigData),  INTENT(IN)  :: config
!         REAL(wp), ALLOCATABLE, INTENT(OUT) :: ws_out(:,:,:) ! (nodes, h_levels, t_steps)

!         INTEGER  :: n_turb, i, j, m, t_step, t_type, n_idx, k_iter
!         REAL(wp) :: v_local, m_ct

!         ! --- SPARSE ARRAYS (For the wake producers) ---
!         INTEGER, ALLOCATABLE :: node_idx(:), type_turb(:), h_idx(:)
        
!         ! --- DENSE ARRAYS (For the grid convergence) ---
!         REAL(wp), ALLOCATABLE :: ws_new(:,:), ws_old(:,:)
!         REAL(wp), ALLOCATABLE :: wake_deficit(:,:), single_deficit(:,:)
        
!         ! 1. Extract Active Turbines to Sparse Arrays
!         n_turb = COUNT(ind%chromosome > 1)
        
!         ! Allocate the master output array
!         ALLOCATE(ws_out(site%n_nodes, site%n_hlevel, site%nsteps))

!         ! Handle Edge Case: Completely empty layout
!         IF (n_turb == 0) THEN
!             ws_out = site%ws0_ts  ! Wind is completely undisturbed
!             RETURN
!         END IF

!         ALLOCATE(node_idx(n_turb), type_turb(n_turb), h_idx(n_turb))
!         ALLOCATE(ws_new(site%n_nodes, site%n_hlevel))
!         ALLOCATE(ws_old(site%n_nodes, site%n_hlevel))
!         ALLOCATE(wake_deficit(site%n_nodes, site%n_hlevel))
!         ALLOCATE(single_deficit(site%n_nodes, site%n_hlevel))

!         ! Build the lookup tables for the wake producers
!         m = 1
!         DO i = 1, site%n_nodes
!             t_type = ind%chromosome(i)
!             IF (t_type > 1) THEN
!                 node_idx(m)  = i
!                 type_turb(m) = t_type
!                 h_idx(m)     = turbines(t_type)%h_idx 
!                 m = m + 1
!             END IF
!         END DO

!         ! --------------------------------------------------------------
!         ! MAIN TIME-STEP LOOP
!         ! --------------------------------------------------------------
!         DO t_step = 1, site%nsteps
            
!             ! Initialize the dense wind field for this time step
!             ws_new = site%ws0_ts(:,:,t_step)
            
!             ! ----------------------------------------------------------
!             ! ALL-TO-ALL ITERATIVE SOLVER
!             ! ----------------------------------------------------------
!             DO k_iter = 1, config%max_iter 
!                 ws_old = ws_new 
!                 wake_deficit = 0.0_wp
                
!                 ! Loop 1: Calculate wakes produced by active turbines
!                 DO m = 1, n_turb
!                     t_type = type_turb(m)
!                     n_idx  = node_idx(m)
                    
!                     ! Local wind speed specifically at the turbine's hub
!                     v_local = ws_new(n_idx, h_idx(m))
                    
!                     m_ct = get_coeff(v_local, turbines(t_type)%v_ref, &
!                                      turbines(t_type)%ct_ref, turbines(t_type)%n_points)
                    
!                     ! Calculate dense deficit field
!                     CALL bastankhah_wake_dense(n_idx, turbines(t_type), m_ct, site, t_step, single_deficit)
                    
!                     wake_deficit = wake_deficit + (single_deficit**2)
!                 END DO

!                 ! Loop 2: Apply the total aggregated wake to the ENTIRE grid
!                 DO i = 1, site%n_nodes
!                     DO j = 1, site%n_hlevel
!                         IF (SQRT(wake_deficit(i, j)) < 1.0_wp) THEN
!                             ws_new(i, j) = site%ws0_ts(i, j, t_step) * (1.0_wp - SQRT(wake_deficit(i, j)))
!                         ELSE
!                             ws_new(i, j) = 0.0_wp
!                         END IF
!                     END DO
!                 END DO

!                 ! Convergence Check (comparing the dense grid)
!                 IF (MAXVAL(ABS(ws_new - ws_old)) < 1.0E-4_wp) EXIT 
!             END DO 
            
!             ! Store the converged 3D slice for this time step
!             ws_out(:,:,t_step) = ws_new
!         END DO

!         DEALLOCATE(node_idx, type_turb, h_idx)
!         DEALLOCATE(ws_new, ws_old, wake_deficit, single_deficit)

!     END SUBROUTINE calculate_3d_wind_field

!     ! ==================================================================
!     ! HELPER FUNCTIONS
!     ! ==================================================================
    ! FUNCTION get_coeff(v_in, v_ref, c_ref, n_pts) RESULT(coeff)
    !     REAL(wp), INTENT(IN) :: v_in
    !     REAL(wp), INTENT(IN) :: v_ref(:), c_ref(:)
    !     INTEGER,  INTENT(IN) :: n_pts
    !     REAL(wp) :: coeff, frac
    !     INTEGER :: i

    !     coeff = 0.0_wp
    !     IF (v_in < v_ref(1) .OR. v_in > v_ref(n_pts)) RETURN

    !     DO i = 1, n_pts - 1
    !         IF (v_in >= v_ref(i) .AND. v_in <= v_ref(i+1)) THEN
    !             frac = (v_in - v_ref(i)) / (v_ref(i+1) - v_ref(i))
    !             coeff = c_ref(i) + frac * (c_ref(i+1) - c_ref(i))
    !             RETURN
    !         END IF
    !     END DO
    ! END FUNCTION get_coeff

! END MODULE power

MODULE NSGA_II

    USE precision, ONLY: wp
    USE types,     ONLY: ConfigData, SiteData, TurbineSpec, Individual, Population
    USE physics,   ONLY: evaluate_physics
    USE costs,     ONLY: evaluate_financial_cost

    IMPLICIT NONE
    PRIVATE

    ! Expose only the high-level genetic operations to the main program
    PUBLIC :: initialize_population
    PUBLIC :: evaluate_population
    PUBLIC :: assign_fitness
    PUBLIC :: create_offspring
    PUBLIC :: merge_populations
    PUBLIC :: select_survivors
    public :: init_random_seed
    PUBLIC :: crossover
    PUBLIC :: mutate

CONTAINS

    ! ! ==================================================================
    ! ! 1. INITIALIZATION & EVALUATION
    ! ! ==================================================================
    ! SUBROUTINE initialize_population(pop, config, site, turbines)
    !     TYPE(Population), INTENT(OUT) :: pop
    !     TYPE(ConfigData), INTENT(IN)  :: config
    !     TYPE(SiteData),   INTENT(IN)  :: site
    !     TYPE(TurbineSpec), INTENT(IN) :: turbines(:)
        
    !     INTEGER  :: i, n_initial, target_node, n_types, random_type
    !     REAL(wp) :: rand_val, rand_type_val
        
    !     ALLOCATE(pop%inds(config%n_pop))
    !     n_types = SIZE(turbines)
        
    !     DO i = 1, config%n_pop
    !         ALLOCATE(pop%inds(i)%chromosome(site%n_nodes))
    !         ALLOCATE(pop%inds(i)%obj_vals(config%n_obj))
            
    !         pop%inds(i)%rank = 0
    !         pop%inds(i)%distance = 0.0_wp
    !         pop%inds(i)%is_valid = .TRUE.
            
    !         ! Start with a completely empty layout (1 = Dummy/Empty Turbine)
    !         pop%inds(i)%chromosome = 1 
            
    !         ! --- BIASED INITIALIZATION ---
    !         CALL RANDOM_NUMBER(rand_val)
    !         n_initial = MAX(1, INT(rand_val * REAL(config%max_turbs, wp)) + 1)
            
    !         ! Ensure we don't accidentally try to place more turbines than available grid nodes
    !         n_initial = MIN(n_initial, config%max_turbs, site%n_nodes)
            
    !         ! Randomly drop turbines into the grid until we hit our target count
    !         DO WHILE (COUNT(pop%inds(i)%chromosome > 1) < n_initial)
    !             CALL RANDOM_NUMBER(rand_val)
    !             target_node = MAX(1, INT(rand_val * REAL(site%n_nodes, wp)) + 1)
                
    !             ! Only place if the node is currently empty (Type 1)
    !             IF (pop%inds(i)%chromosome(target_node) == 1) THEN
                    
    !                 ! Randomly pick a valid type between this gene's specific bounds
    !                 CALL RANDOM_NUMBER(rand_type_val)
                    
    !                 ! Formula: lower + INT(rand * (upper - lower))
    !                 ! We use lb(target_node)+1 to ensure we don't just place another empty dummy
    !                 random_type = (config%lb(target_node) + 1) + &
    !                     INT(rand_type_val * REAL(config%ub(target_node) - config%lb(target_node), wp))
                        
    !                 pop%inds(i)%chromosome(target_node) = random_type
                    
    !             END IF
    !         END DO
    !     END DO
    ! END SUBROUTINE initialize_population

    ! ==================================================================
    ! SUBROUTINE: initialize_population (Biased Density)
    ! Prevents starting the GA behind the max_turbs penalty wall.
    ! ==================================================================
    SUBROUTINE initialize_population(pop, config, site)
        TYPE(Population), INTENT(INOUT) :: pop
        TYPE(ConfigData), INTENT(IN)    :: config
        TYPE(SiteData),   INTENT(IN)    :: site
        
        INTEGER  :: i, j
        REAL(wp) :: rand_val, density
        
        ! Calculate safe density (e.g., aim for max_turbs - 10)
        density = REAL(config%max_turbs - 10, wp) / REAL(site%n_nodes, wp)
        IF (density < 0.001_wp) density = 0.001_wp
        
        ALLOCATE(pop%inds(config%n_pop))
        
        DO i = 1, config%n_pop
            ALLOCATE(pop%inds(i)%chromosome(site%n_nodes))
            ALLOCATE(pop%inds(i)%obj_vals(config%n_obj))
            
            DO j = 1, site%n_nodes
                CALL RANDOM_NUMBER(rand_val)
                
                ! 99% of the time, assign the empty state (lb)
                IF (rand_val > density) THEN
                    pop%inds(i)%chromosome(j) = config%lb(j)
                ELSE
                    ! 1% of the time, pick a random REAL turbine type
                    CALL RANDOM_NUMBER(rand_val)
                    pop%inds(i)%chromosome(j) = (config%lb(j) + 1) + &
                        INT(rand_val * REAL(config%ub(j) - config%lb(j), wp))
                END IF
            END DO
        END DO
    END SUBROUTINE initialize_population

    SUBROUTINE evaluate_population(pop, site, turbines, config)
        TYPE(Population),  INTENT(INOUT) :: pop
        TYPE(SiteData),    INTENT(IN)    :: site
        TYPE(TurbineSpec), INTENT(IN)    :: turbines(:)
        TYPE(ConfigData),  INTENT(IN)    :: config
        INTEGER :: i, n_turb
        
        !$OMP PARALLEL DO DEFAULT(SHARED) PRIVATE(i, n_turb)
        DO i = 1, SIZE(pop%inds)
            n_turb = COUNT(pop%inds(i)%chromosome > 1)
            
            ! Penalty wall
            IF (n_turb > config%max_turbs .or. n_turb < config%min_turbs) THEN
                pop%inds(i)%raw_cost = HUGE(1.0_wp)  ! Massive penalty
                pop%inds(i)%raw_aep  = 0.0_wp        ! Zero energy
                
                pop%inds(i)%obj_vals(1) = HUGE(1.0_wp) 
                pop%inds(i)%obj_vals(2) = HUGE(1.0_wp) 
            ELSE
                ! 1. Calculate raw physics and costs
                CALL evaluate_financial_cost(pop%inds(i), site, turbines, config)
                CALL evaluate_physics(pop%inds(i), site, turbines, config)
                
                ! 2. Explicitly map Objective 1
                SELECT CASE(config%obj_1)
                    CASE(1); pop%inds(i)%obj_vals(1) = pop%inds(i)%raw_cost / &
                        (pop%inds(i)%raw_aep * REAL(config%farmlifetime, wp))
                    CASE(2); pop%inds(i)%obj_vals(1) = pop%inds(i)%raw_cost
                    CASE(3); pop%inds(i)%obj_vals(1) = -pop%inds(i)%raw_aep
                    CASE(4); pop%inds(i)%obj_vals(1) = pop%inds(i)%raw_fatigue
                END SELECT
                
                ! 3. Explicitly map Objective 2
                SELECT CASE(config%obj_2)
                    CASE(1); pop%inds(i)%obj_vals(2) = pop%inds(i)%raw_cost / &
                        (pop%inds(i)%raw_aep * REAL(config%farmlifetime, wp))
                    CASE(2); pop%inds(i)%obj_vals(2) = pop%inds(i)%raw_cost
                    CASE(3); pop%inds(i)%obj_vals(2) = -pop%inds(i)%raw_aep
                    CASE(4); pop%inds(i)%obj_vals(2) = pop%inds(i)%raw_fatigue
                END SELECT
            END IF  
        END DO
        !$OMP END PARALLEL DO
    END SUBROUTINE evaluate_population

    ! ! ==================================================================
    ! ! SUBROUTINE: evaluate_population
    ! ! ==================================================================
    ! SUBROUTINE evaluate_population(pop, site, turbines, config)
    !     TYPE(Population),  INTENT(INOUT) :: pop
    !     TYPE(SiteData),    INTENT(IN)    :: site
    !     TYPE(TurbineSpec), INTENT(IN)    :: turbines(:)
    !     TYPE(ConfigData),  INTENT(IN)    :: config
        
    !     INTEGER :: i, n_turb
    !     REAL(wp) :: total_pa_cost
        
    !     !$OMP PARALLEL DO DEFAULT(SHARED) PRIVATE(i, n_turb, total_pa_cost)
    !     DO i = 1, SIZE(pop%inds)
            
    !         ! 1. Count how many active turbines are in this chromosome
    !         n_turb = COUNT(pop%inds(i)%chromosome > 1)
            
    !         ! 2. THE PENALTY WALL
    !         IF (n_turb > config%max_turbs) THEN
    !             pop%inds(i)%obj_vals(1) = 9.0E15_wp ! Massive Cost
    !             pop%inds(i)%obj_vals(2) = 9.0E15_wp ! Terrible AEP
    !             CYCLE ! Skip the heavy physics entirely!
    !         END IF
            
    !         ! 3. Empty Layout Handling
    !         IF (n_turb == 0) THEN
    !             pop%inds(i)%obj_vals(1) = 0.0_wp
    !             pop%inds(i)%obj_vals(2) = 0.0_wp
    !             CYCLE
    !         END IF
            
    !         ! 4. Normal Evaluation
    !         ! (Assuming you ported calc_pa_cost into mod_kikuchi_costs.f90)
    !         CALL calc_pa_cost(n_turb, pop%inds(i)%chromosome, site%z_coord, turbines, total_pa_cost)
    !         pop%inds(i)%obj_vals(1) = total_pa_cost
            
    !         ! Calculate exact AEP using our PyWake style solver
    !         CALL evaluate_aep(pop%inds(i), site, turbines, config)
            
    !     END DO
    !     !$OMP END PARALLEL DO
    ! END SUBROUTINE evaluate_population
    ! ==================================================================
    ! 2. NSGA-II CORE MECHANICS
    ! ==================================================================
    SUBROUTINE assign_fitness(pop, config)
        TYPE(Population), INTENT(INOUT) :: pop
        TYPE(ConfigData), INTENT(IN)    :: config
        
        CALL fast_non_dominated_sort(pop)
        CALL calculate_crowding_distance(pop, config)
    END SUBROUTINE assign_fitness

    ! ==================================================================
    ! SUBROUTINE: create_offspring (Deterministic Approach)
    ! ==================================================================
    SUBROUTINE create_offspring(parent_pop, offspring_pop, config, turbines)
        TYPE(Population),  INTENT(IN)  :: parent_pop
        TYPE(Population),  INTENT(OUT) :: offspring_pop
        TYPE(ConfigData),  INTENT(IN)  :: config
        TYPE(TurbineSpec), INTENT(IN)  :: turbines(:)

        INTEGER :: n_cross, n_mut, idx, p1, p2, i
        
        ! 1. Calculate deterministic population sizes
        n_cross = 2 * INT(REAL(config%n_pop, wp) * config%p_cross / 2.0_wp)
        n_mut   = INT(REAL(config%n_pop, wp) * config%p_mut)
        
        ! 2. Allocate the offspring population to hold exactly n_cross + n_mut
        ALLOCATE(offspring_pop%inds(n_cross + n_mut))
        DO i = 1, SIZE(offspring_pop%inds)
            ALLOCATE(offspring_pop%inds(i)%chromosome(SIZE(parent_pop%inds(1)%chromosome)))
            ALLOCATE(offspring_pop%inds(i)%obj_vals(config%n_obj))
        END DO
        
        idx = 1
        
        ! --------------------------------------------------------------
        ! 3. CROSSOVER LOOP 
        ! --------------------------------------------------------------
        DO i = 1, n_cross / 2
            p1 = tournament_select(parent_pop)
            p2 = tournament_select(parent_pop)
            
            CALL crossover(parent_pop%inds(p1), parent_pop%inds(p2), &
                           offspring_pop%inds(idx), offspring_pop%inds(idx+1))
            idx = idx + 2
        END DO
        
        ! --------------------------------------------------------------
        ! 4. MUTATION LOOP (Generates 1 child per iteration)
        ! --------------------------------------------------------------
        DO i = 1, n_mut
            p1 = tournament_select(parent_pop)
            
            ! Copy parent chromosome, then mutate the copy
            offspring_pop%inds(idx)%chromosome = parent_pop%inds(p1)%chromosome
            CALL mutate(offspring_pop%inds(idx), config, Turbines)
            idx = idx + 1
        END DO
        
    END SUBROUTINE create_offspring

    ! ==================================================================
    ! SUBROUTINE: merge_populations
    ! Rt = Pt U Qt (Creates an array of size 2N)
    ! ==================================================================
    SUBROUTINE merge_populations(pop1, pop2, combined_pop)
        TYPE(Population), INTENT(IN)  :: pop1, pop2
        TYPE(Population), INTENT(OUT) :: combined_pop
        INTEGER :: n1, n2, i
        
        n1 = SIZE(pop1%inds)
        n2 = SIZE(pop2%inds)
        
        ! Allocate the combined population to hold both parents and children
        IF (ALLOCATED(combined_pop%inds)) DEALLOCATE(combined_pop%inds)
        ALLOCATE(combined_pop%inds(n1 + n2))
        
        ! Modern Fortran automatically deep-copies the dynamic arrays inside the TYPE
        DO i = 1, n1
            combined_pop%inds(i) = pop1%inds(i)
        END DO
        
        DO i = 1, n2
            combined_pop%inds(n1 + i) = pop2%inds(i)
        END DO
    END SUBROUTINE merge_populations

    ! ==================================================================
    ! SUBROUTINE: select_survivors (Elitism)
    ! Sorts combined_pop by Rank and Distance, keeps the top N
    ! ==================================================================
    SUBROUTINE select_survivors(combined_pop, next_pop, config)
        TYPE(Population), INTENT(IN)    :: combined_pop
        TYPE(Population), INTENT(INOUT) :: next_pop
        TYPE(ConfigData), INTENT(IN)    :: config
        
        INTEGER :: i, j, n_comb, temp_idx
        INTEGER, ALLOCATABLE :: sort_idx(:)
        LOGICAL :: is_better
        
        n_comb = SIZE(combined_pop%inds)
        ALLOCATE(sort_idx(n_comb))
        
        ! Initialize the index tracker [1, 2, 3, ..., 2N]
        DO i = 1, n_comb
            sort_idx(i) = i
        END DO
        
        ! 1. Sort the indices (Insertion Sort)
        DO i = 2, n_comb
            temp_idx = sort_idx(i)
            j = i - 1
            
            ! Compare the temp individual against the sorted portion
            DO WHILE (j >= 1)
                is_better = .FALSE.
                
                ! Condition 1: Lower Rank is better
                IF (combined_pop%inds(temp_idx)%rank < combined_pop%inds(sort_idx(j))%rank) THEN
                    is_better = .TRUE.
                    
                ! Condition 2: If Ranks are tied, larger Crowding Distance is better
                ELSE IF (combined_pop%inds(temp_idx)%rank == combined_pop%inds(sort_idx(j))%rank) THEN
                    IF (combined_pop%inds(temp_idx)%distance > combined_pop%inds(sort_idx(j))%distance) THEN
                        is_better = .TRUE.
                    END IF
                END IF
                
                IF (is_better) THEN
                    sort_idx(j + 1) = sort_idx(j)
                    j = j - 1
                ELSE
                    EXIT
                END IF
            END DO
            sort_idx(j + 1) = temp_idx
        END DO
        
        ! 2. Truncate and create the next generation
        IF (.NOT. ALLOCATED(next_pop%inds)) THEN
            ALLOCATE(next_pop%inds(config%n_pop))
        END IF
        
        ! Copy ONLY the top 'n_pop' individuals into the new parent population
        DO i = 1, config%n_pop
            next_pop%inds(i) = combined_pop%inds(sort_idx(i))
        END DO
        
        DEALLOCATE(sort_idx)
    END SUBROUTINE select_survivors

    ! ==================================================================
    ! 3. PRIVATE HELPER ROUTINES 
    ! ==================================================================
    ! ==================================================================
    ! SUBROUTINE: fast_non_dominated_sort (Deb 2002 Algorithm)
    ! ==================================================================
    SUBROUTINE fast_non_dominated_sort(pop)
        TYPE(Population), INTENT(INOUT) :: pop
        
        INTEGER :: n_pop, p, q, i, j
        INTEGER :: current_front_size, next_front_size, current_front_rank
        
        ! Local arrays for Deb's O(MN^2) sorting logic
        INTEGER, ALLOCATABLE :: domination_count(:), s_size(:)
        INTEGER, ALLOCATABLE :: S(:,:), current_front(:), next_front(:)

        n_pop = SIZE(pop%inds)

        ALLOCATE(domination_count(n_pop), s_size(n_pop))
        ALLOCATE(S(n_pop, n_pop), current_front(n_pop), next_front(n_pop))

        ! Initialize helper structures
        domination_count = 0
        s_size = 0
        current_front_size = 0

        ! --------------------------------------------------------------
        ! STEP 1: Find domination counts and sets for every individual
        ! --------------------------------------------------------------
        DO p = 1, n_pop
            DO q = 1, n_pop
                IF (p == q) CYCLE
                
                IF (dominates(pop%inds(p)%obj_vals, pop%inds(q)%obj_vals)) THEN
                    ! 'p' dominates 'q'. Add 'q' to the set of solutions dominated by 'p'.
                    s_size(p) = s_size(p) + 1
                    S(p, s_size(p)) = q
                    
                ELSE IF (dominates(pop%inds(q)%obj_vals, pop%inds(p)%obj_vals)) THEN
                    ! 'q' dominates 'p'. Increment the domination counter of 'p'.
                    domination_count(p) = domination_count(p) + 1
                END IF
            END DO

            ! If no solution dominates 'p', it belongs to the first front (Rank 1)
            IF (domination_count(p) == 0) THEN
                pop%inds(p)%rank = 1
                current_front_size = current_front_size + 1
                current_front(current_front_size) = p
            END IF
        END DO

        ! --------------------------------------------------------------
        ! STEP 2: Iteratively build the subsequent fronts
        ! --------------------------------------------------------------
        current_front_rank = 1

        DO WHILE (current_front_size > 0)
            next_front_size = 0

            ! Loop through everyone in the current front
            DO i = 1, current_front_size
                p = current_front(i)
                
                ! Visit all solutions 'q' that are dominated by 'p'
                DO j = 1, s_size(p)
                    q = S(p, j)
                    domination_count(q) = domination_count(q) - 1
                    
                    ! If 'q' has no more dominators holding it back, it joins the next front
                    IF (domination_count(q) == 0) THEN
                        pop%inds(q)%rank = current_front_rank + 1
                        next_front_size = next_front_size + 1
                        next_front(next_front_size) = q
                    END IF
                END DO
            END DO

            ! Prepare for the next iteration (Replacing the old GOTO logic)
            current_front_rank = current_front_rank + 1
            current_front_size = next_front_size
            current_front(1:current_front_size) = next_front(1:next_front_size)
        END DO

        DEALLOCATE(domination_count, s_size, S, current_front, next_front)
    END SUBROUTINE fast_non_dominated_sort

    ! HELPER FUNCTION: Mathematical domination check (Assumes Minimization)
    PURE FUNCTION dominates(obj_A, obj_B) RESULT(is_dom)
        REAL(wp), INTENT(IN) :: obj_A(:), obj_B(:)
        LOGICAL :: is_dom, strictly_better
        INTEGER :: k
        
        is_dom = .TRUE.
        strictly_better = .FALSE.
        
        DO k = 1, SIZE(obj_A)
            IF (obj_A(k) > obj_B(k)) THEN
                is_dom = .FALSE.  ! A is worse in this objective, cannot dominate
                RETURN
            ELSE IF (obj_A(k) < obj_B(k)) THEN
                strictly_better = .TRUE. ! A is strictly better in this objective
            END IF
        END DO
        
        ! Must be no worse in all, and strictly better in at least one
        is_dom = (is_dom .AND. strictly_better)
    END FUNCTION dominates

    ! ==================================================================
    ! SUBROUTINE: calculate_crowding_distance
    ! ==================================================================
    SUBROUTINE calculate_crowding_distance(pop, config)
        TYPE(Population), INTENT(INOUT) :: pop
        TYPE(ConfigData), INTENT(IN)    :: config
        
        INTEGER :: i, m, n_pop, max_rank, current_front
        REAL(wp) :: obj_max, obj_min, f_range
        
        ! Temporary arrays for the currently evaluated front
        INTEGER, ALLOCATABLE  :: front_idx(:)
        REAL(wp), ALLOCATABLE :: obj_values(:)
        INTEGER :: front_size, f_i
        
        n_pop = SIZE(pop%inds)
        
        ! 1. Reset all distances to 0
        DO i = 1, n_pop
            pop%inds(i)%distance = 0.0_wp
        END DO
        
        ! Find the worst rank to know how many fronts to process
        max_rank = MAXVAL(pop%inds(:)%rank)
        
        ALLOCATE(front_idx(n_pop), obj_values(n_pop))
        
        ! 2. Process one Front at a time
        DO current_front = 1, max_rank
            
            ! Gather all individuals in this specific front
            front_size = 0
            DO i = 1, n_pop
                IF (pop%inds(i)%rank == current_front) THEN
                    front_size = front_size + 1
                    front_idx(front_size) = i
                END IF
            END DO
            
            ! If 1 or 2 individuals, set their distances to infinity and skip
            IF (front_size <= 2) THEN
                DO f_i = 1, front_size
                    pop%inds(front_idx(f_i))%distance = HUGE(1.0_wp)
                END DO
                CYCLE
            END IF
            
            ! 3. Process each objective independently
            DO m = 1, config%n_obj
                
                ! --- OLD SCRIPT OPTIMIZATION: Extract to 1D Array ---
                DO f_i = 1, front_size
                    obj_values(f_i) = pop%inds(front_idx(f_i))%obj_vals(m)
                END DO
                
                ! Sort the front_idx array based on these extracted values
                CALL sort_indices_by_values(obj_values(1:front_size), front_idx(1:front_size))
                
                ! Set boundaries of this sorted list to infinity
                pop%inds(front_idx(1))%distance          = HUGE(1.0_wp)
                pop%inds(front_idx(front_size))%distance = HUGE(1.0_wp)
                
                obj_min = obj_values(1)
                obj_max = obj_values(front_size)
                f_range = obj_max - obj_min
                
                ! Calculate normalized distance for intermediate individuals
                IF (f_range > 1.0E-6_wp) THEN
                    DO f_i = 2, front_size - 1
                        pop%inds(front_idx(f_i))%distance = pop%inds(front_idx(f_i))%distance + &
                            (obj_values(f_i+1) - obj_values(f_i-1)) / f_range
                    END DO
                END IF
            END DO
        END DO
        DEALLOCATE(front_idx, obj_values)
    END SUBROUTINE calculate_crowding_distance

    ! ==================================================================
    ! HELPER: Insertion Sort (Optimized with contiguous 1D array)
    ! ==================================================================
    SUBROUTINE sort_indices_by_values(values, idx_array)
        REAL(wp), INTENT(IN)    :: values(:)
        INTEGER,  INTENT(INOUT) :: idx_array(:)
        
        INTEGER  :: i, j, temp_idx, n
        REAL(wp) :: temp_val
        
        n = SIZE(idx_array)
        DO i = 2, n
            temp_idx = idx_array(i)
            temp_val = values(i)
            j = i - 1
            
            ! Shift elements that are greater than temp_val to the right
            DO WHILE (j >= 1)
                IF (values(j) > temp_val) THEN
                    idx_array(j + 1) = idx_array(j)
                    ! Note: We don't actually swap the 'values' array because 
                    ! we only care about sorting the indices based on the values.
                    j = j - 1
                ELSE
                    EXIT
                END IF
            END DO
            idx_array(j + 1) = temp_idx
        END DO
    END SUBROUTINE sort_indices_by_values

    ! ==================================================================
    ! FUNCTION: tournament_select
    ! Returns the index of the winning parent
    ! ==================================================================
    FUNCTION tournament_select(pop) RESULT(winner_idx)
        TYPE(Population), INTENT(IN) :: pop
        INTEGER :: winner_idx, p1, p2, n_pop
        REAL(wp) :: rand_val
        
        n_pop = SIZE(pop%inds)
        
        ! Randomly select competitor 1
        CALL RANDOM_NUMBER(rand_val)
        p1 = MAX(1, INT(rand_val * REAL(n_pop, wp)) + 1)
        p1 = MIN(p1, n_pop)
        
        ! Randomly select competitor 2
        CALL RANDOM_NUMBER(rand_val)
        p2 = MAX(1, INT(rand_val * REAL(n_pop, wp)) + 1)
        p2 = MIN(p2, n_pop)

        ! Apply Crowded-Comparison Operator
        IF (pop%inds(p1)%rank < pop%inds(p2)%rank) THEN
            winner_idx = p1
        ELSE IF (pop%inds(p2)%rank < pop%inds(p1)%rank) THEN
            winner_idx = p2
        ELSE
            ! Ranks are tied, compare crowding distance (Larger is better)
            IF (pop%inds(p1)%distance > pop%inds(p2)%distance) THEN
                winner_idx = p1
            ELSE
                winner_idx = p2
            END IF
        END IF
    END FUNCTION tournament_select

    ! ==================================================================
    ! SUBROUTINE: crossover (Uniform, 2-Child Output)
    ! ==================================================================
    SUBROUTINE crossover(p1, p2, child1, child2)
        TYPE(Individual), INTENT(IN)  :: p1, p2
        TYPE(Individual), INTENT(INOUT) :: child1, child2
        
        INTEGER  :: i
        REAL(wp) :: rand_val
        
        ! Loop through the layout grid
        DO i = 1, SIZE(p1%chromosome)
            CALL RANDOM_NUMBER(rand_val)
            
            IF (rand_val < 0.5_wp) THEN
                ! Heads: Pass genes straight down
                child1%chromosome(i) = p1%chromosome(i)
                child2%chromosome(i) = p2%chromosome(i)
            ELSE
                ! Tails: Swap the genetic material
                child1%chromosome(i) = p2%chromosome(i)
                child2%chromosome(i) = p1%chromosome(i)
            END IF
        END DO
    END SUBROUTINE crossover

    ! ==================================================================
    ! SUBROUTINE: mutate (Fisher-Yates Logic)
    ! ==================================================================
    SUBROUTINE mutate(ind, config, turbines)
        TYPE(Individual),  INTENT(INOUT) :: ind
        TYPE(ConfigData),  INTENT(IN)    :: config
        TYPE(TurbineSpec), INTENT(IN)    :: turbines(:) 
        
        INTEGER :: i, k, n_mutate, pick, temp, n_var, n_types
        INTEGER, ALLOCATABLE :: gene_indices(:)
        REAL(wp) :: rand_val
        INTEGER  :: step_size
        
        n_var = SIZE(ind%chromosome)
        n_types = SIZE(turbines)
        
        ! 1. Determine how many genes to mutate
        ! (Assuming mu acts as the fraction of genes to alter)
        n_mutate = CEILING(config%mu * REAL(n_var, wp))
        IF (n_mutate < 1) n_mutate = 1
        IF (n_mutate > n_var) n_mutate = n_var
        
        ALLOCATE(gene_indices(n_var))
        DO i = 1, n_var
            gene_indices(i) = i
        END DO
        
        ! 2. Select unique gene indices using partial Fisher-Yates shuffle
        DO i = 1, n_mutate
            CALL RANDOM_NUMBER(rand_val)
            pick = i + INT(rand_val * REAL(n_var - i + 1, wp))
            pick = MIN(pick, n_var) ! Safety clamp
            
            temp = gene_indices(i)
            gene_indices(i) = gene_indices(pick)
            gene_indices(pick) = temp
        END DO
        
        ! 3. Apply Poisson step mutation only to the selected genes
        DO i = 1, n_mutate
            k = gene_indices(i)
            
            ! Generate a Poisson-distributed step
            ! (Using lambda = 1.0. If you have a specific sigma_m array, 
            ! you can pass it into the generator here)
            step_size = poisson_rand(1.0_wp)
            
            ! Randomly choose whether to ADD or SUBTRACT the step
            ! (Standard practice so genes don't all clump at max_var)
            CALL RANDOM_NUMBER(rand_val)
            IF (rand_val < 0.5_wp) THEN
                ind%chromosome(k) = ind%chromosome(k) + step_size
            ELSE
                ind%chromosome(k) = ind%chromosome(k) - step_size
            END IF
        END DO
        
        ! 4. Ensure all genes stay within explicit user-defined bounds
        DO i = 1, n_var
            ind%chromosome(i) = MAX(config%lb(i), ind%chromosome(i))
            ind%chromosome(i) = MIN(config%ub(i), ind%chromosome(i))
        END DO
        
        DEALLOCATE(gene_indices)
    END SUBROUTINE mutate

    ! ==================================================================
    ! HELPER FUNCTION: Knuth's Poisson Random Number Generator
    ! ==================================================================
    FUNCTION poisson_rand(lambda) RESULT(k)
        REAL(wp), INTENT(IN) :: lambda
        INTEGER  :: k
        REAL(wp) :: L, p, u
        
        L = EXP(-lambda)
        k = 0
        p = 1.0_wp
        
        DO WHILE (p > L)
            k = k + 1
            CALL RANDOM_NUMBER(u)
            p = p * u
        END DO
        
        k = k - 1
    END FUNCTION poisson_rand
    ! ==================================================================
    ! SUBROUTINE: init_random_seed
    ! Seeds the PRNG using the system clock to guarantee unique runs.
    ! ==================================================================
    SUBROUTINE init_random_seed()
        INTEGER :: i, n, clock
        INTEGER, ALLOCATABLE :: seed(:)
        
        ! 1. Ask the compiler how big the seed array needs to be
        CALL RANDOM_SEED(SIZE=n)
        ALLOCATE(seed(n))
        
        ! 2. Get the current millisecond from the CPU's internal clock
        CALL SYSTEM_CLOCK(COUNT=clock)
        
        ! 3. Populate the array with the clock data
        ! (Multiplying by a prime number helps spread the entropy)
        seed = clock + 37 * (/ (i - 1, i = 1, n) /)
        
        ! 4. Feed the array back into the Fortran generator
        CALL RANDOM_SEED(PUT=seed)
        
        DEALLOCATE(seed)
    END SUBROUTINE init_random_seed
END MODULE NSGA_II

MODULE SOGA

    USE precision, ONLY: wp
    USE types,     ONLY: ConfigData, SiteData, TurbineSpec, Individual, Population
    USE NSGA_II,   ONLY: crossover, mutate  ! Reuse physical operators
    USE physics,   ONLY: evaluate_physics
    USE costs,     ONLY: evaluate_financial_cost

    IMPLICIT NONE
    PRIVATE

    PUBLIC :: soga_evaluate_population
    PUBLIC :: soga_create_offspring
    PUBLIC :: soga_select_survivors
    PUBLIC :: soga_assign_fitness

CONTAINS

    ! ==================================================================
    ! SUBROUTINE: soga_evaluate_population
    ! Selectively runs ONLY the physics required for the chosen objective
    ! ==================================================================
    SUBROUTINE soga_evaluate_population(pop, site, turbines, config)
        TYPE(Population),  INTENT(INOUT) :: pop
        TYPE(SiteData),    INTENT(IN)    :: site
        TYPE(TurbineSpec), INTENT(IN)    :: turbines(:)
        TYPE(ConfigData),  INTENT(IN)    :: config
        INTEGER :: i, n_turb
        
        !$OMP PARALLEL DO DEFAULT(SHARED) PRIVATE(i, n_turb)
        DO i = 1, SIZE(pop%inds)
            n_turb = COUNT(pop%inds(i)%chromosome > 1)
            
            ! Penalty wall
            IF (n_turb > config%max_turbs .or. n_turb < config%min_turbs) THEN
                ! If invalid, assign terrible fitness instantly and skip physics
                pop%inds(i)%fitness = HUGE(1.0_wp)  
            ELSE
                ! --- LAZY EVALUATION ROUTING ---
                SELECT CASE(config%obj_1)
                    CASE(1) ! LCOE
                        CALL evaluate_financial_cost(pop%inds(i), site, turbines, config)
                        CALL evaluate_physics(pop%inds(i), site, turbines, config)
                        pop%inds(i)%fitness = pop%inds(i)%raw_cost / &
                                            (pop%inds(i)%raw_aep * REAL(config%farmlifetime, wp))
                    CASE(2) ! CAPEX
                        CALL evaluate_financial_cost(pop%inds(i), site, turbines, config)
                        pop%inds(i)%fitness = pop%inds(i)%raw_cost
                    CASE(3) ! AEP
                        CALL evaluate_physics(pop%inds(i), site, turbines, config)
                        pop%inds(i)%fitness = -pop%inds(i)%raw_aep
                    CASE(4) ! Fatigue
                        CALL evaluate_physics(pop%inds(i), site, turbines, config)
                        pop%inds(i)%fitness = pop%inds(i)%raw_fatigue
                END SELECT
                
            END IF  
        END DO
        !$OMP END PARALLEL DO
    END SUBROUTINE soga_evaluate_population

    ! ==================================================================
    ! SUBROUTINE: soga_assign_fitness
    ! Sorts the population based on the fitness already calculated
    ! ==================================================================
    SUBROUTINE soga_assign_fitness(pop)
        TYPE(Population), INTENT(INOUT) :: pop
        INTEGER :: i

        ! 1. Fast 1D Insertion Sort based purely on scalar fitness
        CALL soga_sort_population(pop)
        
        ! 2. Assign artificial Rank 1 to everything so visualization/output tools don't break
        DO i = 1, SIZE(pop%inds)
            pop%inds(i)%rank = 1
        END DO
    END SUBROUTINE soga_assign_fitness

    ! ==================================================================
    ! SUBROUTINE: soga_sort_population
    ! Extremely fast 1D sort replacing the heavy NSGA-II non-dominated sort
    ! ==================================================================
    SUBROUTINE soga_sort_population(pop)
        TYPE(Population), INTENT(INOUT) :: pop
        INTEGER :: i, j
        TYPE(Individual) :: temp_ind

        DO i = 2, SIZE(pop%inds)
            temp_ind = pop%inds(i)
            j = i - 1
            DO WHILE (j >= 1)
                IF (pop%inds(j)%fitness > temp_ind%fitness) THEN
                    pop%inds(j + 1) = pop%inds(j)
                    j = j - 1
                ELSE
                    EXIT
                END IF
            END DO
            pop%inds(j + 1) = temp_ind
        END DO
    END SUBROUTINE soga_sort_population

    ! ==================================================================
    ! SUBROUTINE: soga_create_offspring
    ! Breeds children using Tournament Selection on scalar fitness
    ! ==================================================================
    SUBROUTINE soga_create_offspring(parent_pop, offspring_pop, config, turbines)
        TYPE(Population),  INTENT(IN)  :: parent_pop
        TYPE(Population),  INTENT(OUT) :: offspring_pop
        TYPE(ConfigData),  INTENT(IN)  :: config
        TYPE(TurbineSpec), INTENT(IN)  :: turbines(:)

        INTEGER :: n_cross, n_mut, idx, p1, p2, i
        
        n_cross = 2 * INT(REAL(config%n_pop, wp) * config%p_cross / 2.0_wp)
        n_mut   = INT(REAL(config%n_pop, wp) * config%p_mut)
        
        ALLOCATE(offspring_pop%inds(n_cross + n_mut))
        DO i = 1, SIZE(offspring_pop%inds)
            ALLOCATE(offspring_pop%inds(i)%chromosome(SIZE(parent_pop%inds(1)%chromosome)))
            ALLOCATE(offspring_pop%inds(i)%obj_vals(config%n_obj))
        END DO
        
        idx = 1
        
        ! CROSSOVER LOOP
        DO i = 1, n_cross / 2
            p1 = tournament_select_soga(parent_pop)
            p2 = tournament_select_soga(parent_pop)
            CALL crossover(parent_pop%inds(p1), parent_pop%inds(p2), &
                           offspring_pop%inds(idx), offspring_pop%inds(idx+1))
            idx = idx + 2
        END DO
        
        ! MUTATION LOOP
        DO i = 1, n_mut
            p1 = tournament_select_soga(parent_pop)
            offspring_pop%inds(idx)%chromosome = parent_pop%inds(p1)%chromosome
            CALL mutate(offspring_pop%inds(idx), config, turbines)
            idx = idx + 1
        END DO
    END SUBROUTINE soga_create_offspring

    ! ==================================================================
    ! FUNCTION: tournament_select_soga
    ! Selects the best parent purely based on scalar fitness
    ! ==================================================================
    FUNCTION tournament_select_soga(pop) RESULT(winner_idx)
        TYPE(Population), INTENT(IN) :: pop
        INTEGER :: winner_idx, p1, p2, n_pop
        REAL(wp) :: rand_val
        
        n_pop = SIZE(pop%inds)
        
        CALL RANDOM_NUMBER(rand_val)
        p1 = MAX(1, MIN(INT(rand_val * REAL(n_pop, wp)) + 1, n_pop))
        
        CALL RANDOM_NUMBER(rand_val)
        p2 = MAX(1, MIN(INT(rand_val * REAL(n_pop, wp)) + 1, n_pop))

        ! Winner has the lower (better) fitness
        IF (pop%inds(p1)%fitness < pop%inds(p2)%fitness) THEN
            winner_idx = p1
        ELSE
            winner_idx = p2
        END IF
    END FUNCTION tournament_select_soga

    ! ==================================================================
    ! SUBROUTINE: soga_select_survivors (Strict Elitism)
    ! Since the combined population is sorted, we just take the top N
    ! ==================================================================
    SUBROUTINE soga_select_survivors(combined_pop, next_pop, config)
        TYPE(Population), INTENT(IN)    :: combined_pop
        TYPE(Population), INTENT(INOUT) :: next_pop
        TYPE(ConfigData), INTENT(IN)    :: config
        INTEGER :: i
        
        ! Sort the combined population first
        ! (We need a mutable copy to sort, or we can just rely on assigning fitness)
        ! Assuming soga_assign_fitness was called on combined_pop right before this!

        IF (.NOT. ALLOCATED(next_pop%inds)) THEN
            ALLOCATE(next_pop%inds(config%n_pop))
        END IF
        
        ! Because it is already sorted by fitness, individuals 1 to n_pop are the absolute best
        DO i = 1, config%n_pop
            next_pop%inds(i) = combined_pop%inds(i)
        END DO
    END SUBROUTINE soga_select_survivors

END MODULE SOGA

module outputs
    USE precision, ONLY: wp
    USE types,     ONLY: ConfigData, SiteData, TurbineSpec, Population
    USE physics,   ONLY: calculate_3d_wind_field
    
    implicit none
    PRIVATE

    PUBLIC :: save_generational_front
    PUBLIC :: save_final_pareto
    PUBLIC :: save_animation_data
    public :: cleanup_memory  
    PUBLIC :: soga_save_convergence
    PUBLIC :: soga_save_best_layout
    PUBLIC :: soga_save_animation_data

contains

    SUBROUTINE save_generational_front(gen_num, pop, filename)
        INTEGER,          INTENT(IN) :: gen_num
        TYPE(Population), INTENT(IN) :: pop
        CHARACTER(LEN=*), INTENT(IN) :: filename
        
        INTEGER :: i, f_unit, ios
        
        ! 1. Open File Safely using NEWUNIT
        IF (gen_num == 1) THEN
            ! First generation: Create/Replace the file and write the header
            OPEN(NEWUNIT=f_unit, FILE=filename, STATUS='REPLACE', IOSTAT=ios)
            IF (ios /= 0) THEN
                PRINT *, "🔴 ERROR: Could not create output file: ", TRIM(filename)
                STOP
            END IF
            WRITE(f_unit, '(A)') 'generation,cost_obj1,aep_obj2'
        ELSE
            ! Subsequent generations: Open the existing file and jump to the bottom
            OPEN(NEWUNIT=f_unit, FILE=filename, STATUS='OLD', POSITION='APPEND', IOSTAT=ios)
            IF (ios /= 0) THEN
                PRINT *, "🔴 ERROR: Could not append to output file: ", TRIM(filename)
                STOP
            END IF
        END IF
        
        ! 2. Loop through the population and find Front 1
        DO i = 1, SIZE(pop%inds)
            IF (pop%inds(i)%rank == 1) THEN
                
                ! Write Generation, Cost, and mathematically restored (+AEP)
                WRITE(f_unit, '(I0,A,F25.1,A,F25.1)') &
                    gen_num, ',', pop%inds(i)%obj_vals(1), ',', -pop%inds(i)%obj_vals(2)
            END IF
        END DO
        
        ! 3. Close the file so the OS can safely write the buffer to the hard drive
        CLOSE(f_unit)
        
    END SUBROUTINE save_generational_front

    ! ==================================================================
    ! SUBROUTINE: save_final_pareto
    ! Saves the complete Pareto front (Rank 1) including chromosomes.
    ! ==================================================================
    SUBROUTINE save_final_pareto(pop, filename, config)
        TYPE(Population), INTENT(IN) :: pop
        CHARACTER(LEN=*), INTENT(IN) :: filename
        TYPE(ConfigData), INTENT(IN) :: config

        INTEGER :: i, j, f_unit, ios, n_var

        ! Determine chromosome length dynamically from the first individual
        n_var = SIZE(pop%inds(1)%chromosome)

        ! 1. Open file safely using NEWUNIT
        OPEN(NEWUNIT=f_unit, FILE=filename, STATUS='REPLACE', IOSTAT=ios)
        IF (ios /= 0) THEN
            PRINT *, "🔴 ERROR: Could not create final output file: ", TRIM(filename)
            STOP
        END IF

        ! Write dynamic header
        WRITE(f_unit, '(A)', ADVANCE='NO') 'LCOE,raw_cost,raw_aep,raw_fatigue'
        DO j = 1, n_var
            WRITE(f_unit, '(A,I0)', ADVANCE='NO') ',gene_', j
        END DO
        WRITE(f_unit, *) ! Print a blank line to finish the header row

        ! 3. Loop through the population and find Rank 1
        DO i = 1, SIZE(pop%inds)
            IF (pop%inds(i)%rank == 1) THEN
                
                ! Write Objective 1 (Cost) and Objective 2 (+AEP, mathematically restored)
                WRITE(f_unit, '(F25.1,A,F25.1,A,F25.5,A,F25.5)', ADVANCE='NO') &
                    pop%inds(i)%raw_cost / (pop%inds(i)%raw_aep * REAL(config%farmlifetime, wp)), &
                    ',', pop%inds(i)%raw_cost, ',', pop%inds(i)%raw_aep, ',', &
                    pop%inds(i)%raw_fatigue

                ! Write all the genes of its chromosome on the same line
                DO j = 1, n_var
                    WRITE(f_unit, '(A,I0)', ADVANCE='NO') ',', pop%inds(i)%chromosome(j)
                END DO
                
                WRITE(f_unit, *) ! Finish the line for this individual
            END IF
        END DO

        ! 4. Safely close the file
        CLOSE(f_unit)

        PRINT *, "✅ Final Pareto front successfully saved to: ", TRIM(filename)

    END SUBROUTINE save_final_pareto

    ! ==================================================================
    ! SUBROUTINE: save_animation_data
    ! Finds the best individual for EACH objective and writes a 4D CSV.
    ! ==================================================================
    SUBROUTINE save_animation_data(pop, site, turbines, config)
        TYPE(Population),  INTENT(IN) :: pop
        TYPE(SiteData),    INTENT(IN) :: site
        TYPE(TurbineSpec), INTENT(IN) :: turbines(:)
        TYPE(ConfigData),  INTENT(IN) :: config
        
        INTEGER :: obj_idx, i, j, t_step, best_id, f_unit, ios
        REAL(wp) :: min_val, theta, mag, u_val, v_val
        CHARACTER(LEN=256) :: filename
        
        ! Dynamic array to hold the output from the physics solver
        REAL(wp), ALLOCATABLE :: ws_out(:,:,:)
        
        PRINT *, "----------------------------------------------------"
        PRINT *, "Generating Animation Data for Extreme Objectives:"
        
        ! 1. Loop through every objective configured in the optimizer
        DO obj_idx = 1, config%n_obj
            
            ! --- Find the Best Solution for this Objective ---
            min_val = HUGE(1.0_wp)
            best_id = 1
            
            DO i = 1, SIZE(pop%inds)
                IF (pop%inds(i)%rank == 1) THEN
                    IF (pop%inds(i)%obj_vals(obj_idx) < min_val) THEN
                        min_val = pop%inds(i)%obj_vals(obj_idx)
                        best_id = i
                    END IF
                END IF
            END DO
            
            PRINT *, " -> Obj ", obj_idx, " Best ID: ", best_id, " | Value: ", min_val
            
            ! --- Call the Physics Engine ---
            ! This returns the massive dense grid of dimensions (n_nodes, n_hlevels, nsteps)
            CALL calculate_3d_wind_field(pop%inds(best_id), site, turbines, config, ws_out)
            
            ! --- Prepare Output File ---
            ! Dynamically name the file based on the objective index
            WRITE(filename, '(A, "animation_data_obj_", I0, ".csv")') TRIM(config%out_dir), obj_idx
            
            OPEN(NEWUNIT=f_unit, FILE=TRIM(filename), STATUS='REPLACE', IOSTAT=ios)
            IF (ios /= 0) THEN
                PRINT *, "🔴 ERROR: Could not create animation file: ", TRIM(filename)
                STOP
            END IF
            
            ! --- Write Dynamic Header ---
            WRITE(f_unit, '(A)', ADVANCE='NO') 'time,x,y'
            DO j = 1, site%n_hlevel
                WRITE(f_unit, '(A,I0,A,I0,A,I0)', ADVANCE='NO') ',u_', j, ',v_', j, ',mag_', j
            END DO
            WRITE(f_unit, *) ! Print a final newline to end the header row
            
            ! --- Write Data using Implied DO / No-Advance Logic ---
            DO t_step = 1, site%nsteps
                DO i = 1, site%n_nodes
                    
                    ! Write Time and Node Coordinates
                    WRITE(f_unit, '(I0,A,F12.2,A,F12.2)', ADVANCE='NO') &
                        t_step, ',', site%x_coord(i), ',', site%y_coord(i)
                        
                    ! Get the meteorological wind direction at this specific node and time
                    theta = site%wd0_ts(i, t_step)
                    
                    ! Write U, V, and Mag for every height level on this same row
                    DO j = 1, site%n_hlevel
                        mag = ws_out(i, j, t_step)
                        u_val = mag * COS(theta)
                        v_val = mag * SIN(theta)
                        
                        WRITE(f_unit, '(A,F10.3,A,F10.3,A,F10.3)', ADVANCE='NO') &
                            ',', u_val, ',', v_val, ',', mag
                    END DO
                    
                    WRITE(f_unit, *) ! End the row
                END DO
            END DO
            
            CLOSE(f_unit)
            DEALLOCATE(ws_out) ! Clear memory for the next objective
            
            PRINT *, "    ✅ Saved: ", TRIM(filename)
        END DO
        
        PRINT *, "----------------------------------------------------"
    END SUBROUTINE save_animation_data

    ! ==================================================================
    ! SUBROUTINE: cleanup_memory
    ! Frees all massive RAM allocations before the program terminates.
    ! ==================================================================
    SUBROUTINE cleanup_memory(config, site, turbines, p_pop, o_pop, c_pop)
        TYPE(ConfigData),  INTENT(INOUT) :: config
        TYPE(SiteData),    INTENT(INOUT) :: site
        TYPE(TurbineSpec), ALLOCATABLE, INTENT(INOUT) :: turbines(:)
        TYPE(Population),  INTENT(INOUT) :: p_pop, o_pop, c_pop
        
        INTEGER :: i
        
        ! 1. Free Configuration Arrays
        IF (ALLOCATED(config%lb)) DEALLOCATE(config%lb, config%ub)
        
        ! 2. Free Site Data (The massive 3D wind arrays)
        IF (ALLOCATED(site%x_coord)) DEALLOCATE(site%x_coord, site%y_coord, site%z_coord)
        IF (ALLOCATED(site%h_level)) DEALLOCATE(site%h_level)
        IF (ALLOCATED(site%ws0_ts))  DEALLOCATE(site%ws0_ts, site%wd0_ts)
        
        ! 3. Free Turbine Catalog
        IF (ALLOCATED(turbines)) THEN
            DO i = 1, SIZE(turbines)
                IF (ALLOCATED(turbines(i)%v_ref)) THEN
                    DEALLOCATE(turbines(i)%v_ref, turbines(i)%cp_ref, turbines(i)%ct_ref)
                END IF
            END DO
            DEALLOCATE(turbines)
        END IF
        
        ! 4. Free Populations
        ! (We write a quick helper to clean the deep nested arrays)
        CALL free_population(p_pop)
        CALL free_population(o_pop)
        CALL free_population(c_pop)
        
    END SUBROUTINE cleanup_memory

    ! Helper routine to clean deep nested chromosomes
    SUBROUTINE free_population(pop)
        TYPE(Population), INTENT(INOUT) :: pop
        INTEGER :: i
        IF (ALLOCATED(pop%inds)) THEN
            DO i = 1, SIZE(pop%inds)
                IF (ALLOCATED(pop%inds(i)%chromosome)) DEALLOCATE(pop%inds(i)%chromosome)
                IF (ALLOCATED(pop%inds(i)%obj_vals))   DEALLOCATE(pop%inds(i)%obj_vals)
            END DO
            DEALLOCATE(pop%inds)
        END IF
    END SUBROUTINE free_population

    ! ==================================================================
    ! SOGA OUTPUT 1: Convergence History
    ! ==================================================================
    SUBROUTINE soga_save_convergence(gen_num, pop, filename)
        INTEGER,          INTENT(IN) :: gen_num
        TYPE(Population), INTENT(IN) :: pop
        CHARACTER(LEN=*), INTENT(IN) :: filename
        INTEGER :: f_unit, ios

        IF (gen_num == 1) THEN
            OPEN(NEWUNIT=f_unit, FILE=filename, STATUS='REPLACE', IOSTAT=ios)
            IF (ios /= 0) STOP "🔴 ERROR: Could not create SOGA convergence file."
            WRITE(f_unit, '(A)') 'generation,best_fitness'
        ELSE
            OPEN(NEWUNIT=f_unit, FILE=filename, STATUS='OLD', POSITION='APPEND', IOSTAT=ios)
        END IF

        ! Because soga_assign_fitness sorts the array, index 1 is ALWAYS the absolute best solution.
        WRITE(f_unit, '(I0,A,F25.5)') gen_num, ',', pop%inds(1)%fitness
        CLOSE(f_unit)
    END SUBROUTINE soga_save_convergence

    ! ==================================================================
    ! SOGA OUTPUT 2: The Champion Layout
    ! ==================================================================
    SUBROUTINE soga_save_best_layout(pop, filename)
        TYPE(Population), INTENT(IN) :: pop
        CHARACTER(LEN=*), INTENT(IN) :: filename
        INTEGER :: j, f_unit, ios, n_var

        n_var = SIZE(pop%inds(1)%chromosome)
        OPEN(NEWUNIT=f_unit, FILE=filename, STATUS='REPLACE', IOSTAT=ios)

        WRITE(f_unit, '(A)', ADVANCE='NO') 'fitness'
        DO j = 1, n_var
            WRITE(f_unit, '(A,I0)', ADVANCE='NO') ',gene_', j
        END DO
        WRITE(f_unit, *)

        WRITE(f_unit, '(F25.5)', ADVANCE='NO') pop%inds(1)%fitness
        DO j = 1, n_var
            WRITE(f_unit, '(A,I0)', ADVANCE='NO') ',', pop%inds(1)%chromosome(j)
        END DO
        WRITE(f_unit, *)

        CLOSE(f_unit)
        PRINT *, "✅ Best SOGA layout saved to: ", TRIM(filename)
    END SUBROUTINE soga_save_best_layout

    ! ==================================================================
    ! SOGA OUTPUT 3: Animation Data for the Champion
    ! ==================================================================
    SUBROUTINE soga_save_animation_data(pop, site, turbines, config)
        TYPE(Population),  INTENT(IN) :: pop
        TYPE(SiteData),    INTENT(IN) :: site
        TYPE(TurbineSpec), INTENT(IN) :: turbines(:)
        TYPE(ConfigData),  INTENT(IN) :: config
        INTEGER :: i, j, t_step, f_unit, ios
        REAL(wp) :: theta, mag, u_val, v_val
        REAL(wp), ALLOCATABLE :: ws_out(:,:,:)

        PRINT *, "----------------------------------------------------"
        PRINT *, "Generating SOGA Animation Data for Best Layout..."

        ! Calculate 3D wind field ONLY for the absolute best individual (Index 1)
        CALL calculate_3d_wind_field(pop%inds(1), site, turbines, config, ws_out)

        OPEN(NEWUNIT=f_unit, FILE=TRIM(config%out_dir) // 'animation_data_soga.csv', STATUS='REPLACE', IOSTAT=ios)

        WRITE(f_unit, '(A)', ADVANCE='NO') 'time,x,y'
        DO j = 1, site%n_hlevel
            WRITE(f_unit, '(A,I0,A,I0,A,I0)', ADVANCE='NO') ',u_', j, ',v_', j, ',mag_', j
        END DO
        WRITE(f_unit, *) 

        DO t_step = 1, site%nsteps
            DO i = 1, site%n_nodes
                WRITE(f_unit, '(I0,A,F12.2,A,F12.2)', ADVANCE='NO') &
                    t_step, ',', site%x_coord(i), ',', site%y_coord(i)
                theta = site%wd0_ts(i, t_step)
                DO j = 1, site%n_hlevel
                    mag = ws_out(i, j, t_step)
                    u_val = mag * COS(theta)
                    v_val = mag * SIN(theta)
                    WRITE(f_unit, '(A,F10.3,A,F10.3,A,F10.3)', ADVANCE='NO') &
                        ',', u_val, ',', v_val, ',', mag
                END DO
                WRITE(f_unit, *)
            END DO
        END DO

        CLOSE(f_unit)
        DEALLOCATE(ws_out)
        PRINT *, "    ✅ Saved: ./outputs/animation_data_soga.csv"
        PRINT *, "----------------------------------------------------"
    END SUBROUTINE soga_save_animation_data

end module outputs

