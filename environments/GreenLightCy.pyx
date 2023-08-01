# """
# TODO: We will create a cython class that contains the GreenLight model data structure and functions.
# This class will be used to create a cython module of GreenLight that can be imported into python environment.

# The python environment will send setpoints as actions to the cython module.
# Next, cython will compute the control signals, and simulate the new state of the greenhouse.
# Finally, the new state/measurement/disturbances will be returned to the python environment.
# """

# Import the necessary structs and functions from auxiliaryState.pxd
from auxiliaryStates cimport AuxiliaryStates, update
from defineParameters cimport Parameters, initParameters
from ODE cimport ODE
from utils cimport satVp
from libc.stdlib cimport malloc, free

import numpy as np
cimport numpy as cnp

cnp.import_array()


cdef class GreenLight:
    cdef Parameters* p
    cdef AuxiliaryStates* a
    cdef double (*d)[7]
    # cdef double* u[11]
    cdef double x[27]
    cdef float h
    cdef char timestep

    def __cinit__(self, cnp.ndarray[cnp.double_t, ndim=2] weather, float h):
        self.p = <Parameters*>malloc(sizeof(Parameters))
        self.a = <AuxiliaryStates*>malloc(sizeof(AuxiliaryStates))
        initParameters(self.p)
        self.initWeather(weather)
        self.initStates(self.d[0])
        self.h = h
        self.timestep = 0

    def __dealloc__(self):
        free(self.p)
        free(self.d)

    cpdef step(self, char testIndex):
        """
        Simulate the next time step of the GreenLight model.
        """
        cdef double[11] u
        cdef double *k1 # pointer to a double for our array k1
        cdef char i
        cdef char j

        # Compute the control signals from setpoints
        for i in range(11):
            u[i] = 0.0

        # update auxiliary states
        self.f(u, testIndex)
        self.timestep +=1

    cdef f(self, double[11] u, char testIndex):
        """
        Difference function that computes the next state.
        """
        cdef double* k1
        # cdef double* k2
        # cdef double* k3
        # cdef double* k4
        # cdef char i
        # cdef char j
        # cdef char k
        cdef char l

        # update auxiliary states
        update(self.a, self.p, u, self.x, self.d[self.timestep])
        k1 = ODE(self.a, self.p, self.x, u, self.d[self.timestep])
        for l in range(27):
            print("k1", l, k1[l])

        print("------------------")
        print(self.x[0])

        # Forward Euler
        # cdef char testIndex = 0
        # self.x[testIndex] += self.h * (k1[testIndex])

        # for l in range(1):
            # self.x[l] += self.h * (k1[l])

        # cdef double[27] x2
        # cdef double[27] x3
        # cdef double[27] x4

        # for i in range(27):
        #     x2[i] = self.x[i] + self.h/2*k1[i]

        # # # print("xd k2", x2[0])
        # update(self.a, self.p, u, x2, self.d[0])
        # k2 = ODE(self.a, self.p, x2, u, self.d[0])
        # print("------------------")

        # for j in range(27):
        #     x3[j] = self.x[j] + self.h/2*k2[j]

        # # print("xd k3", x3[0])
        # update(self.a, self.p, u, x3, self.d[0])
        # k3 = ODE(self.a, self.p, x3, u, self.d[0])
        # print("------------------")

        # for k in range(27):
        #     x4[k] = self.x[k] + self.h*k3[k]

        # # print("xd k4", x4[0])
        # update(self.a, self.p, u, x4, self.d[0])
        # k4 = ODE(self.a, self.p, x4, u, self.d[0])
        # print("------------------")

        # self.x[testIndex] += self.h/6 * (k1[testIndex] + 2*k2[testIndex] + 2*k3[testIndex] + k4[testIndex])

        # for l in range(2):
        #     self.x[l] += self.h/6 * (k1[l] + 2*k2[l] + 2*k3[l] + k4[l])

        # print(self.x)
        free(k1)
        # free(k2)
        # free(k3)
        # free(k4)

    cdef void initWeather(self, cnp.ndarray[cnp.double_t, ndim=2] weather):
        """
        Function to initialize the weather data in the cython module of GreenLight.
        We copy the array with weather data that was loaded in by the python environment to an array in the cython module.

        Args:
            weather (np.ndarray): Array with weather data.
        """
        cdef int i, j
        cdef cnp.ndarray[cnp.double_t, ndim=2] np_weather = np.asarray(weather, dtype=np.double)
        cdef int n = np_weather.shape[0]
        self.d = <double(*)[7]>malloc(n * sizeof(double[7]))

        for i in range(n):
            for j in range(7):
                self.d[i][j] = np_weather[i, j]

        # for i in range(105121):
        #     for j in range(9):
        #         self.d[i][j] = weather[i][j]

    cpdef void setStates(self, cnp.ndarray[cnp.double_t, ndim=1] states, char testIndex):
        """
        Function to set the states of the GreenLight model.
        Except for the state that we compute using the model.
        Usefull for testing.
        We copy the array with states that was loaded in by the python environment to an array in the cython module.

        Args:
            states (np.ndarray): Array with states.
        """
        cdef int i
        cdef cnp.ndarray[cnp.double_t, ndim=1] np_states = np.asarray(states, dtype=np.double)
        cdef int n = np_states.shape[0]
        for i in range(n):
            if i != testIndex:
                self.x[i] = np_states[i]

    cdef void initStates(self, double[7] d0):
        """
        CO2 concentration is equal to outdoor CO2	
        x[0]: co2Air CO2 concentration in main air compartment [mg m^{-3}]
        x[1]: co2Top CO2 concentration in top air compartment [mg m^{-3}]
        x[2]: tAir  Air temperature in main compartment [deg C]
        x[3]: tTop  Air temperature in top compartment [deg C]
        x[4]: tCan  Temperature of the canopy [deg C]
        x[5]: tCovIn Indoor cover temperature [deg C]
        x[6]: tCovE  Outdoor cover temperature [deg C]
        x[7]: tThScr Thermal screen temperature [deg C]
        x[8]: tFlr   Floor temperature [deg C]
        x[9]: tPipe  Pipe temperature [deg C]
        x[10]: tSoil1    First soil layer temperature [deg C]
        x[11]: tSoil2    Second soil layer temperature [deg C]
        x[12]: tSoil3    Third soil layer temperature [deg C]
        x[13]: tSoil4    Fourth soil layer temperature [deg C]
        x[14]: tSoil5    Fifth soil layer temperature [deg C]
        x[15]: vpAir Vapor pressure of main air compartment [Pa]
        x[16]: vpTop Vapor pressure of top air compartment [Pa]
        x[17]: tLamp Lamp temperature [deg C]
        x[18]: tIntLamp   Interlight temperature [deg C]
        x[19]: tGroPipe   Grow pipe temperature [deg C]
        x[20]: tBlScr    Blackout screen temperature [deg C]
        x[21]: tCan24    Average temperature of the canopy over last 24 hours [deg C]
        
        x[22]: cBuf  Carbohydrates in crop buffer [mg{CH20} m^{-2}]
        x[23]: cLeaf Carbohydrates in leaves [mg{CH20} m^{-2}]
        x[24]: cStem Carbohydrates in stem [mg{CH20} m^{-2}]
        x[25]: cFruit    Carbohydrates in fruit [mg{CH20} m^{-2}]
        x[26]: tCanSum   Crop development stage [C day]
    """
        # self.x = <double(*)[26]>malloc(sizeof(double))
        # Air and vapor pressure are assumed to start at the night setpoints
        # x.co2Air.val = d.co2Out.val(1,2)
        self.x[0] = d0[3] # co2Air
        
        # x.co2Top.val = x.co2Air.val
        self.x[1] = self.x[0] # co2Top
        
        # x.tAir.val = p.tSpNight.val
        self.x[2] = self.p.tSpNight # tAir
        
        # x.tTop.val = x.tAir.val
        self.x[3] = self.x[2] # tTop

        # x.tCan.val = x.tAir.val+4
        self.x[4] = self.x[2] + 4

        # x.tCovIn.val = x.tAir.val
        self.x[5] = self.x[2]

        # x.tCovE.val = x.tAir.val
        self.x[6] = self.x[2]

        # x.tThScr.val = x.tAir.val
        self.x[7] = self.x[2]

        # x.tFlr.val = x.tAir.val
        self.x[8] = self.x[2]

        # x.tPipe.val = x.tAir.val
        self.x[9] = self.x[2]
        
        # x.tSo1.val = x.tAir.val
        self.x[10] = self.x[2]
        
        # x.tSo2.val = 1/4*(3*x.tAir.val+d.tSoOut.val(1,2))
        self.x[11] = 1/4*(3*self.x[2]*d0[6])

        # # x.tSo3.val = 1/4*(2*x.tAir.val+2*d.tSoOut.val(1,2))
        self.x[12] = 1/4*(2*self.x[2]+2*d0[6])

        # # x.tSo4.val = 1/4*(x.tAir.val+3*d.tSoOut.val(1,2))
        self.x[13] = 1/4*(self.x[2]+3*d0[6])

        # # x.tSo5.val = d.tSoOut.val(1,2)
        self.x[14] = d0[6]
        
        # # x.vpAir.val = p.rhMax.val/100*satVp(x.tAir.val)
        self.x[15] = self.p.rhMax/100*satVp(self.x[2])

        # # x.vpTop.val = x.vpAir.val
        self.x[16] = self.x[15]

        # # x.tLamp.val = x.tAir.val
        self.x[17] = self.x[2]

        # # x.tIntLamp.val = x.tAir.val
        self.x[18] = self.x[2]

        # # x.tGroPipe.val = x.tAir.val
        self.x[19] = self.x[2]

        # # x.tBlScr.val = x.tAir.val
        self.x[20] = self.x[2]
        
        # x.tCan24.val = x.tCan.val
        self.x[21] = self.x[4]

        ## crop model
        # x.cBuf.val = 0
        self.x[22] = 0

        # # start with 3.12 plants/m2, assume they are each 2 g = 6240 mg/m2.
        # x.cLeaf.val = 0.7*6240; # 70# in leafs
        # x.cStem.val = 0.25*6240; # 25# in stems
        # x.cFruit.val = 0.05*6240; # 5# in fruits we only harvest if this is > 300K so lets start with fully grown plants instead.

        self.x[23] = 0.7*6240
        self.x[24] = 0.25*6240
        self.x[25] = 0.05*6240

        # # x.tCanSum.val = 0
        self.x[26] = 0


        # the time variable is taken from m.t
        # x.time.val = datenum(getDefStr(gl.t))      
        # Time - start with the datenum of when the simulation starts
        # x.time.val = datenum(gl.t.label)
        
        ##    
        # gl.x = x


    def getWeatherArray(self):
        """
        Function that copies weather data from the cython module to a numpy array.
        Such that we can acces the weather data in the python environment.
        Currently copies complete array with weather data, but this can be changed to only copy the relevant data.
        For example, a future weather prediction.
        """
        cdef int n = 105121
        cdef int m = 7
        cdef  cnp.ndarray[cnp.double_t, ndim=2] np_d = np.zeros((n, m), dtype=np.double)
        for i in range(n):
            for j in range(m):
                np_d[i, j] = self.d[i][j]
        return np_d

    def getStatesArray(self):
        """
        Function that copies the states from the cython module to a numpy array.
        Such that we can acces the states in the python environment.
        """
        cdef int n = 27
        cdef  cnp.ndarray[cnp.double_t, ndim=1] np_x = np.zeros(n, dtype=np.double)
        for i in range(n):
            np_x[i] = self.x[i]
        return np_x


    property alfaLeafAir:
        def __get__(self):
            return self.p.alfaLeafAir

# cpdef compute_auxiliary_state():
    # GL = GreenLight()
    # return GL

    # # Create an instance of the AuxiliaryState struct
    # cdef Parameters p
    # cdef AuxiliaryStates a

    # cdef char nu = 11
    # cdef char nx = 27
    # cdef char nd = 8
    # cdef char i
    # cdef char j
    # cdef char k

    # cdef float u[6] # cannot use nu here because that is not a constant, could use dynamic memory allocation
    # # cdef float* u = <float*>malloc(nu*sizeof(float)) # later on this would be freed via free(u)
    # cdef float x[27] # cannot use nx due to similar reason as above
    # cdef float d[8] # cannot use nd due to similar reason as above

    # for i in range(nu):
    #     u[i] = 1.0

    # for j in range(nx):
    #     x[j] = 1.0

    # for k in range(nd):
    #     d[k] = weather[k]

    # # Initialize the Parameters struct
    # initParameters(&p)

    # print("begin")
    # # Compute the auxiliary states
    # update(&a, &p, u, x, d)
    # print(a.tauShScrPar)
    # print("heat capacity cover:", a.capCov)
