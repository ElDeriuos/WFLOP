! Release check: built with the same static flags as the programs (make omp_check
! STATIC=1), it proves the statically linked OpenMP runtime starts real threads.
! Prints the number of threads that actually ran the parallel region.
PROGRAM omp_check
    USE omp_lib
    IMPLICIT NONE
    INTEGER :: n
    n = 0
    !$OMP PARALLEL
    !$OMP ATOMIC
    n = n + 1
    !$OMP END PARALLEL
    PRINT '(A,I0)', 'threads=', n
END PROGRAM omp_check
