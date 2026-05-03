MODULE mod_types
    USE mod_precision, ONLY: wp
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
        integer  :: min_turbs    ! Minimum allowable turbines
        INTEGER  :: n_obj        ! Number of objectives (1 or 2+)
        Integer  :: max_iter     ! Maximum iterations for All2AllIterative
        INTEGER, ALLOCATABLE :: lb(:)  ! Lower bounds for each gene (node)
        INTEGER, ALLOCATABLE :: ub(:)  ! Upper bounds for each gene (node)
        real(wp):: workability   ! The percentage of time the weather allows construction
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
        REAL(wp), ALLOCATABLE :: obj_vals(:)   ! Objective outputs (Cost, -AEP)
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

END MODULE mod_types