import sys,subprocess
from os import environ as env
import os

def cmake_istrue(s):
   return not (s.upper() in ("FALSE", "OFF", "NO") or s.upper().endswith("-NOTFOUND"))

def error(s):
   print(s)
   exit(1)

# if jenkins issue 12438 is resolved, options would be directly passed as args=env
# until then none of the OPTIONS key or values (including the host name)
# are allowed to contain space or = characters.
args = dict(map(lambda x: x.split("="), env["OPTIONS"].split(" ")))

#get all "GMX_" variables
opts = dict((k,v) for k,v in args.iteritems() if k.startswith("GMX_"))

env_cmd = "true"
build_cmd = "make -j2"
test_cmd = "ctest -DExperimentalTest -V"
call_opts = {}
opts_list = ""
    
if "CMakeVersion" in args:
   env["PATH"] =  "%s/tools/cmake-%s/bin:%s" % (env["HOME"],args["CMakeVersion"],env["PATH"])

if not 'Compiler' in args or not 'CompilerVersion' in args or not 'host' in args:
   error("Compiler, CompilerVersion and host needs to be specified")

if args['Compiler']=="gcc":
   env["CC"]  = "gcc-"      + args["CompilerVersion"]
   env["CXX"] = "g++-"      + args["CompilerVersion"]
   env["FC"]  = "gfortran-" + args["CompilerVersion"]

if args['Compiler']=="clang":
   env["CC"]  = "clang"
   env["CXX"] = "clang++"

if args['Compiler']=="icc":
   if args["host"].lower().find("win")>-1:
      env_cmd = '"c:\\Program Files (x86)\\Microsoft Visual Studio 9.0\\VC\\vcvarsall.bat" amd64 && "c:\\Program Files (x86)\\Intel\\Composer XE\\bin\\compilervars.bat" intel64 vs2008shell'
      env["CC"]  = "icl"
      env["CXX"] = "icl"
   else:
      env_cmd = ". /opt/intel/bin/iccvars.sh intel64"
      env["CC"]  = "icc"
      env["CXX"] = "icpc"

if args['Compiler']=="msvc":
   if args['CompilerVersion']=='2008':
      env_cmd = '"c:\\Program Files (x86)\\Microsoft Visual Studio 9.0\\VC\\vcvarsall.bat" x86'
   elif args['CompilerVersion']=='2010':
      env_cmd = '"c:\\Program Files (x86)\\Microsoft Visual Studio 10.0\\VC\\vcvarsall.bat" amd64'
   else:
      error("MSVC only version 2008 and 2010 supported")

if "GMX_EXTERNAL" in opts.keys():
    v = opts.pop("GMX_EXTERNAL")
    opts["GMX_EXTERNAL_LAPACK"] = v
    opts["GMX_EXTERNAL_BLAS"] = v
    if cmake_istrue(v):
       if "Compiler" in args and args['Compiler']=="icc":
          opts_list += '-DGMX_FFT_LIBRARY=mkl  -DMKL_LIBRARIES="${MKLROOT}/lib/intel64/libmkl_intel_lp64.so;${MKLROOT}/lib/intel64/libmkl_sequential.so;${MKLROOT}/lib/intel64/libmkl_core.so" -DMKL_INCLUDE_DIR=${MKLROOT}/include '
       else:
          env["CMAKE_LIBRARY_PATH"] = "/usr/lib/atlas-base"

#forcing to use OpenMPI because FindMPI in 4.5 has a bug with MPICH
if "GMX_MPI" in opts.keys() and cmake_istrue(opts["GMX_MPI"]):
    opts_list += '-DMPI_COMPILER=`which mpicc.openmpi` '  

if not args["host"].lower().find("win")>-1:
   call_opts = {"executable":"/bin/bash"}
else:
   opts_list += '-G "NMake Makefiles JOM" '
   build_cmd = "jom -j4"

if args["host"].lower().find("mac")>-1:
   env["CMAKE_PREFIX_PATH"] = "/opt/local"

#construct string for all "GMX_" variables
opts_list += " ".join(["-D%s=%s"%(k,v) for k,v in opts.iteritems()])
opts_list += " -DGMX_DEFAULT_SUFFIX=off -DCMAKE_BUILD_TYPE=Debug ."

ret = 0

def call_cmd(cmd):
   print "Running " + cmd
   return subprocess.call(cmd, stdout=sys.stdout, stderr=sys.stderr, shell=True, **call_opts)

if env['GERRIT_PROJECT']=='releng':
   if 'GROMACS_REFSPEC' in env: gromacs_refspec = env['GROMACS_REFSPEC']
   else: gromacs_refspec = 'refs/heads/release-4-5-patches'
   cmd = 'git init && git fetch git://git.gromacs.org/gromacs.git %s && git checkout -q -f FETCH_HEAD && git clean -fd'%(gromacs_refspec,)
   ret |= call_cmd(cmd)

call_cmd("git gc")

cmd = "%s && cmake --version && cmake %s && %s && %s" % (env_cmd,opts_list,build_cmd,test_cmd)

ret |= call_cmd(cmd)

if not os.path.exists("regressiontests"): os.makedirs("regressiontests")

os.chdir("regressiontests")
if 'REGRESSIONTESTS_REFSPEC' in env: regression_refspec = env['REGRESSIONTESTS_REFSPEC']
else: regression_refspec = 'refs/heads/release-4-5'

cmd = 'git init && git fetch git://git.gromacs.org/regressiontests.git %s && git checkout -q -f FETCH_HEAD && git clean -fd'%(regression_refspec,)
print "Running " + cmd
ret |= call_cmd(cmd)


cmd = '%s && perl gmxtest.pl -mpirun mpirun.openmpi -xml -nosuffix all' % (env_cmd,)
if args["host"].lower().find("win")>-1: 
   env['PATH']+=';C:\\MinGW\\msys\\1.0\\bin'
env['PATH']=os.pathsep.join([env['PATH']]+map(os.path.abspath,["../src/kernel","../src/tools"]))
if "GMX_MPI" in opts.keys() and cmake_istrue(opts["GMX_MPI"]):
   cmd += ' -np 2'
if "GMX_DOUBLE" in opts.keys() and cmake_istrue(opts["GMX_DOUBLE"]):
   cmd += ' -double'
ret |= call_cmd(cmd)

sys.exit(ret)


