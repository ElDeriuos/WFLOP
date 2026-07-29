PROGRAM run_simulator
    USE simulation, ONLY: simulate_solution_file
    IMPLICIT NONE
    CHARACTER(LEN=512) :: config_file, solution_file, selector
    INTEGER, ALLOCATABLE :: selected_rows(:)
    INTEGER :: argc

    argc = COMMAND_ARGUMENT_COUNT()
    IF (argc < 2 .OR. argc > 3) THEN
        PRINT *, 'Usage: run_simulator <config.inp> <solutions.csv> <rows|all>'
        PRINT *, 'Rows are 1-based data-row numbers; use comma-separated values, e.g. 1,4,7.'
        STOP 2
    END IF
    CALL GET_COMMAND_ARGUMENT(1, config_file)
    CALL GET_COMMAND_ARGUMENT(2, solution_file)
    IF (argc == 2) THEN
        ALLOCATE(selected_rows(0))
    ELSE
        CALL GET_COMMAND_ARGUMENT(3, selector)
        CALL parse_row_selector(TRIM(selector), selected_rows)
    END IF
    CALL simulate_solution_file(TRIM(config_file), TRIM(solution_file), selected_rows)

CONTAINS

    SUBROUTINE parse_row_selector(text, rows)
        CHARACTER(LEN=*), INTENT(IN) :: text
        INTEGER, ALLOCATABLE, INTENT(OUT) :: rows(:)
        CHARACTER(LEN=64) :: token
        INTEGER :: i, start, finish, n, value, ios
        IF (TRIM(text) == 'all') THEN
            ALLOCATE(rows(0))
            RETURN
        END IF
        n = 1
        DO i = 1, LEN_TRIM(text)
            IF (text(i:i) == ',') n = n + 1
        END DO
        ALLOCATE(rows(n)); rows = 0
        start = 1; n = 0
        DO i = 1, LEN_TRIM(text) + 1
            IF (i > LEN_TRIM(text) .OR. text(i:i) == ',') THEN
                finish = i - 1
                IF (finish < start) THEN
                    PRINT *, 'ERROR: empty row selector.'
                    STOP 2
                END IF
                token = ' '; token = text(start:finish)
                READ(token, *, IOSTAT=ios) value
                IF (ios /= 0 .OR. value < 1) THEN
                    PRINT *, 'ERROR: invalid row selector: ', TRIM(token)
                    STOP 2
                END IF
                n = n + 1; rows(n) = value
                start = i + 1
            END IF
        END DO
    END SUBROUTINE parse_row_selector
END PROGRAM run_simulator
