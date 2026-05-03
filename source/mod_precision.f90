MODULE mod_precision
    USE, INTRINSIC :: iso_fortran_env, ONLY: real64
    IMPLICIT NONE
    
    ! Define 'wp' (Working Precision) as standard 64-bit float.
    ! Usage: REAL(wp) :: my_variable
    INTEGER, PARAMETER :: wp = real64

END MODULE mod_precision