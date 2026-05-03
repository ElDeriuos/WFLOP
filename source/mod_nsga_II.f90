MODULE mod_NSGA_II

    USE mod_precision, ONLY: wp
    USE mod_types,     ONLY: ConfigData, SiteData, TurbineSpec, Individual, Population
    USE mod_physics,   ONLY: evaluate_aep
    USE mod_costs,     ONLY: evaluate_financial_cost

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
        
        !$OMP PARALLEL DO DEFAULT(SHARED) PRIVATE(i)
        DO i = 1, SIZE(pop%inds)
            n_turb = COUNT(pop%inds(i)%chromosome > 1)
            IF (n_turb > config%max_turbs .or. n_turb < config%min_turbs) THEN
                pop%inds(i)%obj_vals(1) = huge(1.0_wp)  ! Massive positive Cost
                pop%inds(i)%obj_vals(2) = huge(1.0_wp)  ! Massive positive (terrible) AEP
            ELSE
                CALL evaluate_financial_cost(pop%inds(i), site, turbines, config)
                CALL evaluate_aep(pop%inds(i), site, turbines, config)
            end if  
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
END MODULE mod_NSGA_II


    