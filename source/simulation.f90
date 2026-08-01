MODULE simulation
    USE precision, ONLY: wp
    USE types, ONLY: ConfigData, SiteData, TurbineSpec, Individual
    USE inputs, ONLY: read_gui_config, load_turbines, load_site_data
    USE physics, ONLY: evaluate_physics
    USE costs, ONLY: evaluate_financial_cost
    IMPLICIT NONE
    PRIVATE

    PUBLIC :: simulate_solution_file

CONTAINS

    SUBROUTINE simulate_solution_file(config_filename, solution_filename, selected_rows)
        CHARACTER(LEN=*), INTENT(IN) :: config_filename, solution_filename
        INTEGER, INTENT(IN) :: selected_rows(:)
        TYPE(ConfigData) :: config
        TYPE(SiteData) :: site
        TYPE(TurbineSpec), ALLOCATABLE :: turbines(:)
        TYPE(Individual) :: ind
        INTEGER :: f_in, ios, row_number, n_fields, n_genes, i, j, n_selected
        INTEGER, ALLOCATABLE :: gene_columns(:), fields_gene(:)
        CHARACTER(LEN=2048) :: line
        CHARACTER(LEN=512), ALLOCATABLE :: fields(:)
        LOGICAL :: header_found, selected, first_output
        INTEGER :: f_ts, f_summary, f_turbines, f_json
        REAL(wp), ALLOCATABLE :: farm_power(:), farm_cf(:), turbine_mean(:), turbine_max(:)
        REAL(wp), ALLOCATABLE :: turbine_total(:), turbine_speed(:,:), turbine_ref_power(:,:)
        REAL(wp), ALLOCATABLE :: turbine_ti(:), turbine_ct(:), turbine_thrust(:)
        REAL(wp) :: installed_capacity, total_energy, reference_energy, wake_loss
        REAL(wp) :: lcoe, mean_power, max_power, annual_energy
        INTEGER :: n_turb, t, node, t_type

        CALL read_gui_config(config_filename, config)
        config%wind_mode = 1
        CALL load_turbines(config%f_turb, turbines, site)
        CALL load_site_data(config%f_wind1, config%f_wind2, config%f_bathy, config%f_dist, site, config)

        CALL execute_command_line('mkdir -p "' // TRIM(config%out_dir) // '"')
        OPEN(NEWUNIT=f_in, FILE=solution_filename, STATUS='OLD', ACTION='READ', IOSTAT=ios)
        IF (ios /= 0) STOP 'ERROR: Could not open solution CSV.'

        READ(f_in, '(A)', IOSTAT=ios) line
        IF (ios /= 0) STOP 'ERROR: Solution CSV has no header.'
        CALL split_csv(line, fields, n_fields)
        ALLOCATE(gene_columns(site%n_nodes))
        gene_columns = 0
        n_genes = 0
        DO i = 1, n_fields
            IF (INDEX(ADJUSTL(fields(i)), 'gene_') == 1) THEN
                n_genes = n_genes + 1
                IF (n_genes <= site%n_nodes) gene_columns(n_genes) = i
            END IF
        END DO
        IF (n_genes < site%n_nodes) THEN
            PRINT *, 'WARNING: solution CSV has fewer gene columns than mesh nodes; row skipped.'
        END IF

        OPEN(NEWUNIT=f_ts, FILE=TRIM(config%out_dir)//'simulation_farm_timeseries.csv', STATUS='REPLACE')
        OPEN(NEWUNIT=f_summary, FILE=TRIM(config%out_dir)//'simulation_summary.csv', STATUS='REPLACE')
        OPEN(NEWUNIT=f_turbines, FILE=TRIM(config%out_dir)//'simulation_turbines.csv', STATUS='REPLACE')
        OPEN(NEWUNIT=f_json, FILE=TRIM(config%out_dir)//'simulation_summary.json', STATUS='REPLACE')
        WRITE(f_ts,'(A)') 'solution_id,source_row,timestep,total_power_kw,total_capacity_factor'
        WRITE(f_summary,'(A)') 'solution_id,source_row,installed_turbines,installed_capacity_mw,mean_power_kw,max_power_kw,annual_energy_gwh,capacity_factor,wake_loss_percent,raw_cost,raw_aep_gwh,raw_fatigue,lcoe'
        WRITE(f_turbines,'(A)') 'solution_id,source_row,turbine_index,node_id,turbine_type,mean_power_kw,max_power_kw,total_power_kwh,mean_effective_speed_ms,mean_wake_free_power_kw,mean_turbulence_intensity,mean_ct,mean_thrust_n'
        WRITE(f_json,'(A)') '['
        first_output = .TRUE.
        row_number = 0

        DO
            READ(f_in, '(A)', IOSTAT=ios) line
            IF (ios /= 0) EXIT
            IF (LEN_TRIM(line) == 0) CYCLE
            row_number = row_number + 1
            CALL split_csv(line, fields, n_fields)
            selected = row_is_selected(row_number, selected_rows)
            IF (.NOT. selected) CYCLE
            IF (n_genes < site%n_nodes) THEN
                PRINT *, 'WARNING: skipping malformed solution row ', row_number
                CYCLE
            END IF

            n_turb = 0
            DO i = 1, site%n_nodes
                READ(fields(gene_columns(i)), *, IOSTAT=ios) j
                IF (ios /= 0 .OR. j < 1 .OR. j > site%n_types) THEN
                    PRINT *, 'WARNING: invalid turbine type in source row ', row_number, '; row skipped.'
                    n_turb = -1
                    EXIT
                END IF
                IF (j > 1) n_turb = n_turb + 1
            END DO
            IF (n_turb < 0) CYCLE
            IF (n_turb == 0) THEN
                PRINT *, 'WARNING: source row ', row_number, ' contains no turbines; row skipped.'
                CYCLE
            END IF

            ALLOCATE(ind%chromosome(site%n_nodes))
            DO i = 1, site%n_nodes
                READ(fields(gene_columns(i)), *) ind%chromosome(i)
            END DO
            ALLOCATE(farm_power(site%nsteps), farm_cf(site%nsteps))
            ALLOCATE(turbine_mean(n_turb), turbine_max(n_turb), turbine_total(n_turb))
            ALLOCATE(turbine_speed(n_turb,site%nsteps), turbine_ref_power(n_turb,site%nsteps))
            ALLOCATE(turbine_ti(n_turb), turbine_ct(n_turb), turbine_thrust(n_turb))
            CALL evaluate_financial_cost(ind, site, turbines, config)
            CALL evaluate_physics(ind, site, turbines, config, farm_power, farm_cf, turbine_mean, &
                                  turbine_max, turbine_total, turbine_speed, turbine_ref_power, &
                                  turbine_ti, turbine_ct, turbine_thrust)

            installed_capacity = 0.0_wp
            j = 0
            DO i = 1, site%n_nodes
                t_type = ind%chromosome(i)
                IF (t_type > 1) THEN
                    j = j + 1
                    installed_capacity = installed_capacity + turbines(t_type)%rated_power
                    WRITE(f_turbines,'(I0,A,I0,A,I0,A,I0,A,I0,A,F0.6,A,F0.6,A,F0.6,A,F0.6,A,F0.6,A,F0.6,A,F0.6,A,F0.6)') &
                        solution_number(row_number, selected_rows), ',', row_number, ',', j, ',', i, ',', t_type, ',', &
                        turbine_mean(j), ',', turbine_max(j), ',', turbine_total(j), ',', &
                        SUM(turbine_speed(j,:))/REAL(site%nsteps,wp), ',', &
                        SUM(turbine_ref_power(j,:))/REAL(site%nsteps,wp), ',', turbine_ti(j), ',', &
                        turbine_ct(j), ',', turbine_thrust(j)
                END IF
            END DO
            total_energy = SUM(farm_power)
            reference_energy = SUM(turbine_ref_power)
            wake_loss = 0.0_wp
            IF (reference_energy > 0.0_wp) wake_loss = 100.0_wp * (1.0_wp - total_energy/reference_energy)
            mean_power = total_energy / REAL(site%nsteps,wp)
            max_power = MAXVAL(farm_power)
            annual_energy = ind%raw_aep
            lcoe = 0.0_wp
            IF (annual_energy > 0.0_wp) lcoe = ind%raw_cost / (annual_energy * REAL(config%farmlifetime,wp))

            DO t = 1, site%nsteps
                WRITE(f_ts,'(I0,A,I0,A,I0,A,F0.6,A,F0.6)') solution_number(row_number, selected_rows), ',', row_number, ',', t, ',', farm_power(t), ',', farm_cf(t)
            END DO
            WRITE(f_summary,'(I0,A,I0,A,I0,A,F0.6,A,F0.6,A,F0.6,A,F0.6,A,F0.6,A,F0.6,A,F0.6,A,F0.6,A,F0.6,A,F0.6,A,F0.6)') &
                solution_number(row_number, selected_rows), ',', row_number, ',', n_turb, ',', installed_capacity, ',', mean_power, ',', &
                max_power, ',', annual_energy, ',', mean_power/installed_capacity, ',', wake_loss, ',', ind%raw_cost, ',', &
                ind%raw_aep, ',', ind%raw_fatigue, ',', lcoe
            CALL write_json_solution(f_json, first_output, row_number, solution_number(row_number, selected_rows), &
                                     n_turb, installed_capacity, mean_power, max_power, annual_energy, &
                                     mean_power/installed_capacity, wake_loss, ind%raw_cost, ind%raw_aep, ind%raw_fatigue, lcoe)
            first_output = .FALSE.

            DEALLOCATE(ind%chromosome, farm_power, farm_cf, turbine_mean, turbine_max, turbine_total, &
                       turbine_speed, turbine_ref_power, turbine_ti, turbine_ct, turbine_thrust)
        END DO
        WRITE(f_json,'(A)') ']'
        CLOSE(f_in); CLOSE(f_ts); CLOSE(f_summary); CLOSE(f_turbines); CLOSE(f_json)
        CALL cleanup_site(site, turbines, config)
        PRINT *, 'Simulation completed. Outputs written to ', TRIM(config%out_dir)
    END SUBROUTINE simulate_solution_file

    INTEGER FUNCTION solution_number(row_number, selected_rows) RESULT(value)
        INTEGER, INTENT(IN) :: row_number, selected_rows(:)
        INTEGER :: i
        IF (SIZE(selected_rows) == 0) THEN
            value = row_number
            RETURN
        END IF
        value = 0
        DO i = 1, SIZE(selected_rows)
            IF (selected_rows(i) == row_number) THEN
                value = i
                RETURN
            END IF
        END DO
    END FUNCTION solution_number

    LOGICAL FUNCTION row_is_selected(row_number, selected_rows) RESULT(value)
        INTEGER, INTENT(IN) :: row_number, selected_rows(:)
        IF (SIZE(selected_rows) == 0) THEN
            value = .TRUE.
        ELSE
            value = ANY(selected_rows == row_number)
        END IF
    END FUNCTION row_is_selected

    SUBROUTINE split_csv(line, fields, n_fields)
        CHARACTER(LEN=*), INTENT(IN) :: line
        CHARACTER(LEN=512), ALLOCATABLE, INTENT(OUT) :: fields(:)
        INTEGER, INTENT(OUT) :: n_fields
        INTEGER :: i, start, finish, count
        count = 1
        DO i = 1, LEN_TRIM(line)
            IF (line(i:i) == ',') count = count + 1
        END DO
        ALLOCATE(fields(count)); fields = ' '
        start = 1; n_fields = 0
        DO i = 1, LEN_TRIM(line) + 1
            IF (i > LEN_TRIM(line) .OR. line(i:i) == ',') THEN
                n_fields = n_fields + 1
                finish = i - 1
                IF (finish >= start) fields(n_fields) = ADJUSTL(line(start:finish))
                start = i + 1
            END IF
        END DO
    END SUBROUTINE split_csv

    SUBROUTINE write_json_solution(unit, first, source_row, solution_id, n_turb, capacity, mean_p, max_p, annual_e, cf, wake, cost, aep, fatigue, lcoe)
        INTEGER, INTENT(IN) :: unit, source_row, solution_id, n_turb
        LOGICAL, INTENT(INOUT) :: first
        REAL(wp), INTENT(IN) :: capacity, mean_p, max_p, annual_e, cf, wake, cost, aep, fatigue, lcoe
        IF (.NOT. first) WRITE(unit,'(A)') ','
        WRITE(unit,'(A,I0,A,I0,A,I0,A,ES16.8,A,ES16.8,A,ES16.8,A,ES16.8,A,ES16.8,A,ES16.8,A,ES16.8,A,ES16.8,A,ES16.8,A,ES16.8,A)') &
            '  {"solution_id":', solution_id, ',"source_row":', source_row, ',"installed_turbines":', n_turb, &
            ',"installed_capacity_mw":', capacity, ',"mean_power_kw":', mean_p, ',"max_power_kw":', max_p, &
            ',"annual_energy_gwh":', annual_e, ',"capacity_factor":', cf, ',"wake_loss_percent":', wake, &
            ',"raw_cost":', cost, ',"raw_aep_gwh":', aep, ',"raw_fatigue":', fatigue, ',"lcoe":', lcoe, '}'
    END SUBROUTINE write_json_solution

    SUBROUTINE cleanup_site(site, turbines, config)
        TYPE(SiteData), INTENT(INOUT) :: site
        TYPE(TurbineSpec), ALLOCATABLE, INTENT(INOUT) :: turbines(:)
        TYPE(ConfigData), INTENT(INOUT) :: config
        INTEGER :: i
        IF (ALLOCATED(config%lb)) DEALLOCATE(config%lb, config%ub)
        IF (ALLOCATED(site%x_coord)) DEALLOCATE(site%x_coord, site%y_coord, site%z_coord)
        IF (ALLOCATED(site%h_level)) DEALLOCATE(site%h_level)
        IF (ALLOCATED(site%ws0_ts)) DEALLOCATE(site%ws0_ts, site%wd0_ts)
        IF (ALLOCATED(turbines)) THEN
            DO i = 1, SIZE(turbines)
                IF (ALLOCATED(turbines(i)%v_ref)) DEALLOCATE(turbines(i)%v_ref, turbines(i)%cp_ref, turbines(i)%ct_ref)
            END DO
            DEALLOCATE(turbines)
        END IF
    END SUBROUTINE cleanup_site
END MODULE simulation
