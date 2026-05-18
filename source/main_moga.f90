PROGRAM run_moga

    ! ------------------------------------------------------------------
    ! MODULE IMPORTS 
    ! ------------------------------------------------------------------
    USE types                         ! Contains our TYPE definitions
    USE inputs                              ! Reading Files
    use outputs                            ! Writing files
    USE physics                       ! Wake models and AEP
    USE NSGA_II                       ! GA / NSGA-II mechanisms
    
    IMPLICIT NONE

    ! ------------------------------------------------------------------
    ! VARIABLE DECLARATIONS (Using Modern Derived Types)
    ! ------------------------------------------------------------------
    TYPE(ConfigData)    :: config         ! GUI parameters (it_max, n_pop, etc.)
    TYPE(SiteData)      :: site           ! Mesh, Bathymetry, Wind time-series
    TYPE(TurbineSpec), ALLOCATABLE :: turbines(:) ! Array of available turbine types
    
    TYPE(Population)    :: parent_pop     ! Current generation (Pt)
    TYPE(Population)    :: offspring_pop  ! New children (Qt)
    TYPE(Population)    :: combined_pop   ! Merged population (Rt)
    
    INTEGER :: generation

    ! ------------------------------------------------------------------
    ! PHASE 1: INITIALIZATION & SETUP
    ! ------------------------------------------------------------------
    PRINT *, "Starting Wind Farm Optimizer (NSGA-II)..."
    
    ! 1. Read GUI configurations
    CALL read_gui_config('./inputs/config.inp', config)
    
    ! 2. Load static data
    CALL load_turbines(config%f_turb, turbines, site)
    CALL load_site_data(config%f_wind, config%f_bathy, config%f_dist, site, config)

    ! 3. Generate and evaluate the initial random population (P0)
    CALL init_random_seed()                     
    CALL initialize_population(parent_pop, config, site)
    CALL evaluate_population(parent_pop, site, turbines, config)
    
    ! 4. Perform the first non-dominated sort and assign crowding distance
    CALL assign_fitness(parent_pop, config)

    ! ------------------------------------------------------------------
    ! PHASE 2: MAIN EVOLUTIONARY LOOP (NSGA-II)
    ! ------------------------------------------------------------------
    PRINT *, "Entering evolutionary loop..."
    
    DO generation = 1, config%it_max
        PRINT *, "--- Generation ", generation, " of ", config%it_max, " ---"
        
        ! 1. Breed new solutions (Crossover & Mutation)
        CALL create_offspring(parent_pop, offspring_pop, config, turbines)
        
        ! 2. Evaluate the new children
        CALL evaluate_population(offspring_pop, site, turbines, config)
        
        ! 3. Merge parents and children (Rt = Pt U Qt)
        CALL merge_populations(parent_pop, offspring_pop, combined_pop)
        
        ! 4. Sort the combined population and assign fitness
        CALL assign_fitness(combined_pop, config)
        
        ! 5. Elitist survival selection (Build Pt+1)
        CALL select_survivors(combined_pop, parent_pop, config)
        
        ! 6. Save tracking data for the GUI (Convergence plotting)
        CALL save_generational_front(generation, parent_pop, &
                TRIM(config%out_dir) // 'generational_fronts.csv', config)
        
    END DO

    ! ------------------------------------------------------------------
    ! PHASE 3: POST-PROCESSING & CLEANUP
    ! ------------------------------------------------------------------
    PRINT *, "Optimization complete. Saving final outputs..."
  
    ! 1. Save the final Pareto front for the GUI 2D/3D viewers
    PRINT *, "Saving final Pareto front..."
    CALL save_final_pareto(parent_pop, TRIM(config%out_dir) // 'final_pareto_front.csv', config)

    ! 2. Auto-select the best cost solution and generate 4D wind field
    CALL save_animation_data(parent_pop, site, turbines, config)
    
    ! 3. Free all memory to prevent leaks
    CALL cleanup_memory(config, site, turbines, parent_pop, offspring_pop, combined_pop)
    
    PRINT *, "Run finished successfully."

END PROGRAM run_moga


