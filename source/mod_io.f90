MODULE mod_io

    USE mod_precision, ONLY: wp
    USE mod_types,     ONLY: ConfigData, SiteData, TurbineSpec, Population
    USE mod_physics,   ONLY: calculate_3d_wind_field
    
    IMPLICIT NONE
    PRIVATE   ! Hide everything by default

    ! Only allow the main program to call these specific subroutines
    PUBLIC :: read_gui_config
    PUBLIC :: load_site_data
    PUBLIC :: load_turbines
    PUBLIC :: save_generational_front
    PUBLIC :: save_final_pareto
    PUBLIC :: save_animation_data
    public :: cleanup_memory

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
        Read(f_unit, *) config%workability
!        READ(f_unit, *) config%max_iter
        CLOSE(f_unit)

        ! Defaulting to 2 objectives (Cost and AEP). We can tie this to the GUI later.
        config%n_obj = 2
        config%max_iter = 10
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
        REAL(wp) :: dummy_real, xc, yc
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
    ! SUBROUTINE: save_generational_front
    ! Saves Rank 1 individuals (Pareto front) to track GA convergence.
    ! ==================================================================
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
    SUBROUTINE save_final_pareto(pop, filename)
        TYPE(Population), INTENT(IN) :: pop
        CHARACTER(LEN=*), INTENT(IN) :: filename

        INTEGER :: i, j, f_unit, ios, n_var

        ! Determine chromosome length dynamically from the first individual
        n_var = SIZE(pop%inds(1)%chromosome)

        ! 1. Open file safely using NEWUNIT
        OPEN(NEWUNIT=f_unit, FILE=filename, STATUS='REPLACE', IOSTAT=ios)
        IF (ios /= 0) THEN
            PRINT *, "🔴 ERROR: Could not create final output file: ", TRIM(filename)
            STOP
        END IF

        ! 2. Write dynamic header for the CSV file
        WRITE(f_unit, '(A)', ADVANCE='NO') 'cost_obj1,aep_obj2'
        DO j = 1, n_var
            WRITE(f_unit, '(A,I0)', ADVANCE='NO') ',gene_', j
        END DO
        WRITE(f_unit, *) ! Print a blank line to finish the header row

        ! 3. Loop through the population and find Rank 1
        DO i = 1, SIZE(pop%inds)
            IF (pop%inds(i)%rank == 1) THEN
                
                ! Write Objective 1 (Cost) and Objective 2 (+AEP, mathematically restored)
                WRITE(f_unit, '(F25.1,A,F25.1)', ADVANCE='NO') &
                    pop%inds(i)%obj_vals(1), ',', -pop%inds(i)%obj_vals(2)

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
            WRITE(filename, '("../outputs/animation_data_obj_", I0, ".csv")') obj_idx
            
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

END MODULE mod_io