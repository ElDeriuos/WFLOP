FC = gfortran
FFLAGS ?= -O2 -fopenmp -ffree-line-length-none
BUILD ?= build

CORE_OBJ = $(BUILD)/wflop_core.o
SIM_OBJ = $(BUILD)/simulation.o
SIM_MAIN_OBJ = $(BUILD)/main_simulator.o
SOGA_MAIN_OBJ = $(BUILD)/main_soga.o
MOGA_MAIN_OBJ = $(BUILD)/main_moga.o
SIM_EXE = $(BUILD)/simulator
SOGA_EXE = $(BUILD)/soga_optimizer
MOGA_EXE = $(BUILD)/moga_optimizer
# Legacy mesher, run by the GUI's mesh step
POLY_EXE = $(BUILD)/polygon3

.PHONY: all simulator soga_optimizer moga_optimizer polygon3 clean

all: simulator soga_optimizer moga_optimizer polygon3

polygon3: $(POLY_EXE)

simulator: $(SIM_EXE)

soga_optimizer: $(SOGA_EXE)

moga_optimizer: $(MOGA_EXE)

$(BUILD):
	mkdir -p $(BUILD)

$(CORE_OBJ): source/wflop_core.f90 | $(BUILD)
	$(FC) $(FFLAGS) -J$(BUILD) -I$(BUILD) -c $< -o $@

$(SIM_OBJ): source/simulation.f90 $(CORE_OBJ) | $(BUILD)
	$(FC) $(FFLAGS) -J$(BUILD) -I$(BUILD) -c $< -o $@

$(SIM_MAIN_OBJ): source/main_simulator.f90 $(SIM_OBJ) | $(BUILD)
	$(FC) $(FFLAGS) -J$(BUILD) -I$(BUILD) -c $< -o $@

$(SOGA_MAIN_OBJ): source/main_soga.f90 $(CORE_OBJ) | $(BUILD)
	$(FC) $(FFLAGS) -J$(BUILD) -I$(BUILD) -c $< -o $@

$(MOGA_MAIN_OBJ): source/main_moga.f90 $(CORE_OBJ) | $(BUILD)
	$(FC) $(FFLAGS) -J$(BUILD) -I$(BUILD) -c $< -o $@

$(SIM_EXE): $(CORE_OBJ) $(SIM_OBJ) $(SIM_MAIN_OBJ)
	$(FC) $(FFLAGS) -o $@ $^

$(SOGA_EXE): $(CORE_OBJ) $(SOGA_MAIN_OBJ)
	$(FC) $(FFLAGS) -o $@ $^

$(MOGA_EXE): $(CORE_OBJ) $(MOGA_MAIN_OBJ)
	$(FC) $(FFLAGS) -o $@ $^

$(POLY_EXE): source/polygon3.for | $(BUILD)
	$(FC) -ffixed-form -fno-automatic -O3 -fopenmp $< -o $@

clean:
	rm -rf $(BUILD)
	rm -f source/*.mod source/*.mod0
