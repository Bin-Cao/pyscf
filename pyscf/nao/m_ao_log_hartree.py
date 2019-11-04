# Copyright 2014-2018 The PySCF Developers. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import division, print_function
from pyscf.nao.m_sbt import sbt_c
import numpy as np
import copy
 
#
#
#
def ao_log_hartree_lap_libnao(ao):
  """
    Computes radial parts of Hartree potentials generated by the radial orbitals using Laplace transform (r_>, r_<)
    Uses a call to Fortran version of the calculation.
    Args: 
      self: class instance of ao_log_c
    Result:
      ao_pot with respective radial parts
  """
  from ctypes import POINTER, c_double, c_int64
  from pyscf.nao.ao_log import ao_log
  from pyscf.nao.m_libnao import libnao

  libnao.ao_hartree_lap.argtypes = (
    POINTER(c_double), # rr(nr)
    POINTER(c_int64),  # nmult
    POINTER(c_double), # mu2ff(nr,nmult)
    POINTER(c_int64),  # nr
    POINTER(c_int64),  # mu2j
    POINTER(c_double)) # mu2vh(nr,nmult)

  ao_pot = ao_log(ao_log=ao)

  rr = np.require(ao.rr, dtype=c_double, requirements='C')  
  for sp in range(ao.nspecies):
    mu2j = np.require(ao.sp_mu2j[sp], dtype=c_int64, requirements='C')
    ff_rad = np.require(ao.psi_log[sp], dtype=c_double, requirements='C')
    ff_pot = np.require(ao_pot.psi_log[sp], dtype=c_double, requirements='CW')
    
    libnao.ao_hartree_lap(
      rr.ctypes.data_as(POINTER(c_double)), 
      c_int64(ao.sp2nmult[sp]),
      ff_rad.ctypes.data_as(POINTER(c_double)), 
      c_int64(ao.nr),
      mu2j.ctypes.data_as(POINTER(c_int64)),
      ff_pot.ctypes.data_as(POINTER(c_double)))
      
    ao_pot.psi_log[sp] = ff_pot  
    for mu,am in enumerate(ao.sp_mu2j[sp]):
        ao_pot.psi_log_rl[sp][mu,:] = ao_pot.psi_log[sp][mu,:]/(ao.rr**am)

  for sp in range(ao.nspecies): ao_pot.sp_mu2rcut[sp].fill(ao.rr[-1])
  ao_pot.sp2rcut.fill(ao.rr[-1])

  return ao_pot
  
#
#
#
def ao_log_hartree_sbt(ao):
  """
    Computes radial parts of Hartree potentials generated by the radial orbitals using the spherical Bessel transform
    Args: 
      self: class instance of ao_log
    Result:
      ao_pot with respective radial parts
  """
  sbt = sbt_c(ao.rr, ao.pp, lmax=ao.jmx)
  
  ao_pot = copy.deepcopy(ao)
  for sp,mu2ff in enumerate(ao.psi_log):
    for mu,[ff,am] in enumerate(zip(mu2ff, ao.sp_mu2j[sp])):
      ao_pot.psi_log[sp][mu,:] = (4*np.pi) * sbt.sbt( sbt.sbt( ff, am, 1)/ao.pp**2, am, -1)
      ao_pot.psi_log_rl[sp][mu,:] = ao_pot.psi_log[sp][mu,:]/(ao.rr**am)

  for sp in range(ao.nspecies): ao_pot.sp_mu2rcut[sp].fill(ao.rr[-1])
  ao_pot.sp2rcut.fill(ao.rr[-1])
  
  return ao_pot

#
#
#
def ao_log_hartree_lap(ao):
  """
    Computes radial parts of Hartree potentials generated by the radial orbitals using Laplace transform (r_>, r_<)
    Args: 
      self: class instance of ao_log_c
    Result:
      ao_pot with respective radial parts
  """
  ao_pot = copy.deepcopy(ao)
  dr = np.log(ao.rr[1]/ao.rr[0])
  vff = np.zeros(ao.nr)
  for sp,mu2ff in enumerate(ao.psi_log):
    for mu,[ff,am] in enumerate(zip(mu2ff, ao.sp_mu2j[sp])):
      ffrr3 = ff*ao.rr**3
      vff.fill(0.0)
      for ir in range(ao.nr):
        for irp in range(ao.nr):
          rrl = min(ao.rr[ir], ao.rr[irp])**am
          rrg = max(ao.rr[ir], ao.rr[irp])**(am+1)
          vff[ir] = vff[ir] + rrl/rrg * ffrr3[irp]
          
      ao_pot.psi_log[sp][mu,:] = (4*np.pi*dr)/(2*am+1.0) * vff
      ao_pot.psi_log_rl[sp][mu,:] = ao_pot.psi_log[sp][mu,:]/(ao.rr**am)

  for sp in range(ao.nspecies): ao_pot.sp_mu2rcut[sp].fill(ao.rr[-1])
  ao_pot.sp2rcut.fill(ao.rr[-1])

  return ao_pot

#
#
#
def ao_log_hartree(ao, ao_log_hartree_method='lap'):
  if ao_log_hartree_method.upper()=='LAP': return ao_log_hartree_lap_libnao(ao)
  if ao_log_hartree_method.upper()=='SBT': return ao_log_hartree_sbt(ao)
  raise RuntimeError('!method')

#
#
#
if __name__ == '__main__':
  from pyscf.nao.m_system_vars import system_vars_c
  import matplotlib.pyplot as plt
  
  sv = system_vars_c('siesta')
  
  ao_h_lap = ao_log_hartree(sv.ao_log, ao_log_hartree_method='lap')
  ao_h_sbt = ao_log_hartree(sv.ao_log, ao_log_hartree_method='sbt')

  sp = 0
  for mu,[ff_lap,ff_sbt,j] in enumerate(zip(ao_h_lap.psi_log[sp], ao_h_sbt.psi_log[sp], ao_h_sbt.sp_mu2j[sp])):
    nc = abs(ff_lap).max()
    if j==0 : 
      plt.plot(ao_h_lap.rr, ff_lap/nc, '--', label=str(mu)+' j='+str(j))
      plt.plot(ao_h_lap.rr, ff_sbt/nc, '.-', label=str(mu)+' j='+str(j))
    if j>0 : 
      plt.plot(ao_h_lap.rr, ff_lap/nc, '--', label=str(mu)+' j='+str(j))
      plt.plot(ao_h_lap.rr, ff_sbt/nc, '.-', label=str(mu)+' j='+str(j))

  plt.legend()
  plt.xlim(0.0,2.0)
  plt.ylim(0.8,1.1)
  plt.show()
  
  
