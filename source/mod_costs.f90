MODULE mod_costs

    USE mod_precision, ONLY: wp
    USE mod_types,     ONLY: SiteData, TurbineSpec, Individual, ConfigData

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
        ind%obj_vals(1) = dcpa_cost + cable_cost + inc_cost
        
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

END MODULE mod_costs