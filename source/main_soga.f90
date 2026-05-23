PROGRAM run_soga

    USE types
    USE inputs
    USE outputs
    USE SOGA
    USE NSGA_II, ONLY: init_random_seed, initialize_population, merge_populations
    
    IMPLICIT NONE

    TYPE(ConfigData)    :: config
    TYPE(SiteData)      :: site
    TYPE(TurbineSpec), ALLOCATABLE :: turbines(:)
    TYPE(Population)    :: parent_pop, offspring_pop, combined_pop
    INTEGER :: generation

    PRINT *, "Starting Single-Objective Optimizer (SOGA)..."
    
    ! 1. Read Configurations
    CALL read_gui_config('./inputs/config.inp', config)
    CALL load_turbines(config%f_turb, turbines, site)
    CALL load_site_data(config%f_wind1, config%f_wind2, config%f_bathy, config%f_dist, site, config)

    ! 2. Initialize and Evaluate First Generation
    CALL init_random_seed()                     
    CALL initialize_population(parent_pop, config, site)
    CALL soga_evaluate_population(parent_pop, site, turbines, config)
    CALL soga_assign_fitness(parent_pop)

    PRINT *, "Entering evolutionary loop..."
    
    ! 3. Main Evolutionary Loop
    DO generation = 1, config%it_max
        PRINT *, "--- Generation ", generation, " of ", config%it_max, " ---"
        
        CALL soga_create_offspring(parent_pop, offspring_pop, config, turbines)
        CALL soga_evaluate_population(offspring_pop, site, turbines, config)
        
        CALL merge_populations(parent_pop, offspring_pop, combined_pop)
        CALL soga_assign_fitness(combined_pop)
        CALL soga_select_survivors(combined_pop, parent_pop, config)
        
        ! Save Convergence History
        CALL soga_save_convergence(generation, parent_pop, TRIM(config%out_dir) // 'soga_convergence.csv')
    END DO

    PRINT *, "Optimization complete. Saving final outputs..."
    
    ! 4. Save Final SOGA Outputs
    CALL soga_save_best_layout(parent_pop, TRIM(config%out_dir) // 'soga_best_layout.csv')
    CALL soga_save_animation_data(parent_pop, site, turbines, config)
    
    CALL cleanup_memory(config, site, turbines, parent_pop, offspring_pop, combined_pop)
    
    PRINT *, "Single-Objective Genetic Algorithm Run finished successfully."

END PROGRAM run_soga