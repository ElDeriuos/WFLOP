FC = gfortran
FFLAGS ?= -O2 -fopenmp -ffree-line-length-none
BUILD ?= build

# Link flags. `make STATIC=1` (used for releases) links the GCC runtime
# (libgfortran, libquadmath, libgcc, libgomp) into the programs, so they run,
# OpenMP included, on machines without gfortran installed.
LDFLAGS = -fopenmp
ifeq ($(STATIC),1)
  ifeq ($(OS),Windows_NT)
    LDFLAGS = -fopenmp -static
  else
    # libquadmath (used by libgfortran) and libgomp are linked from their static
    # archives. Older GCCs (Ubuntu 22.04, Homebrew) still add a dynamic -lquadmath;
    # --as-needed / -dead_strip_dylibs drops it because nothing uses it any more.
    ifeq ($(shell uname -s),Darwin)
      DROP_UNUSED = -Wl,-dead_strip_dylibs
    else
      DROP_UNUSED = -Wl,--as-needed
    endif
    # -print-file-name returns the bare name when an archive is not installed
    static_lib = $(filter /%,$(shell $(FC) -print-file-name=$(1)))
    LDFLAGS = $(DROP_UNUSED) -static-libgfortran -static-libgcc \
              $(call static_lib,libquadmath.a) $(call static_lib,libgomp.a) -lpthread
  endif
endif

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

.PHONY: all simulator soga_optimizer moga_optimizer polygon3 omp_check clean

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
	$(FC) -o $@ $^ $(LDFLAGS)

$(SOGA_EXE): $(CORE_OBJ) $(SOGA_MAIN_OBJ)
	$(FC) -o $@ $^ $(LDFLAGS)

$(MOGA_EXE): $(CORE_OBJ) $(MOGA_MAIN_OBJ)
	$(FC) -o $@ $^ $(LDFLAGS)

# polygon3 has no OpenMP directives, so it is built without -fopenmp
$(POLY_EXE): source/polygon3.for | $(BUILD)
	$(FC) -ffixed-form -fno-automatic -O3 $< -o $@ $(filter-out -fopenmp,$(LDFLAGS))

# Release check that the (static) OpenMP runtime runs threads; not part of `all`
omp_check: tests/omp_check.f90 | $(BUILD)
	$(FC) -fopenmp -J$(BUILD) -c $< -o $(BUILD)/omp_check.o
	$(FC) -o $(BUILD)/omp_check $(BUILD)/omp_check.o $(LDFLAGS)

clean:
	rm -rf $(BUILD)
	rm -f source/*.mod source/*.mod0
