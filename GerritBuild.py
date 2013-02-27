import sys,subprocess,platform
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
use_asan = False
    
if "CMakeVersion" in args:
   env["PATH"] =  "%s/tools/cmake-%s/bin:%s" % (env["HOME"],args["CMakeVersion"],env["PATH"])

if not 'Compiler' in args or not 'CompilerVersion' in args or not 'host' in args:
   error("Compiler, CompilerVersion and host needs to be specified")

if args['Compiler']=="gcc":
   env["CC"]  = "gcc-"      + args["CompilerVersion"]
   env["CXX"] = "g++-"      + args["CompilerVersion"]
   env["FC"]  = "gfortran-" + args["CompilerVersion"]

if args['Compiler']=="clang":
   env["CC"]  = "clang-"    + args["CompilerVersion"]
   env["CXX"] = "clang++-"  + args["CompilerVersion"]
   if 'CompilerFlags' in args and args["CompilerFlags"]=="ASAN":
      #bit ugly to hard code this here but way to long to pass all from Jenkins
      opts_list += '-DCMAKE_C_FLAGS_DEBUG="-g -O1 -faddress-sanitizer -fno-omit-frame-pointer" -DCMAKE_CXX_FLAGS_DEBUG="-g -O1 -faddress-sanitizer -fno-omit-frame-pointer" -DCMAKE_EXE_LINKER_FLAGS_DEBUG=-faddress-sanitizer -DCUDA_PROPAGATE_HOST_FLAGS=no '
      opts_list += '-DBUILD_SHARED_LIBS=no ' #http://code.google.com/p/address-sanitizer/issues/detail?id=38
      use_asan = True

if args['Compiler']=="icc":
   if args["host"].lower().find("win")>-1:
      env_cmd = '"c:\\Program Files (x86)\\Microsoft Visual Studio 10.0\\VC\\vcvarsall.bat" amd64 && "c:\\Program Files (x86)\\Intel\\Composer XE\\bin\\compilervars.bat" intel64 vs2010'
      env["CC"]  = "icl"
      env["CXX"] = "icl"
      #remove incremental which is added by cmake to avoid warning
      opts_list += '-DCMAKE_EXE_LINKER_FLAGS="/STACK:10000000 /machine:x64" ' 
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

use_gpu = use_mpi = use_tmpi = False
if "GMX_GPU" in opts.keys() and cmake_istrue(opts["GMX_GPU"]):
   use_gpu = True
if "GMX_MPI" in opts.keys() and cmake_istrue(opts["GMX_MPI"]):
   use_mpi = True
if not use_mpi and (not "GMX_THREAD_MPI" in opts.keys() or cmake_istrue(opts["GMX_THREAD_MPI"])):
   use_tmpi = True


if use_mpi:
   if "CompilerVersion" in args:
      env["OMPI_CC"] =env["CC"]
      env["OMPI_CXX"]=env["CXX"]
      if "FC" in env:
         env["OMPI_FC"] =env["FC"]
   env["CC"] ="mpicc"
   env["CXX"]="mpic++"
   env["FC"] ="mpif90"
   # set the nvcc host compiler; normally CXX should be used, but nvcc <=v5.0
   # does not recognize icpc, only icc. To avoid a lot of if-else code here, as
   # a C compiler works just fine, we'll use CC
   # if we happen to be using a non-supported compiler (e.g with clang address-
   # sanitizer builds, we'll just use the default compiler)
   if use_gpu and (args['Compiler']=="icc" or args['Compiler']=="gcc") and not "win" in platform.platform().lower():
      # this will only work on *NIX, but for now that's good enough
      p = subprocess.Popen(["which", env["OMPI_CC"]],stdout=subprocess.PIPE)
      stdout =  p.communicate()[0]
      ompi_cc_full = stdout.rstrip()
      opts_list += ' -DCUDA_HOST_COMPILER=%s ' % ompi_cc_full
      if p.returncode != 0:
         sys.exit("Could not determine the full path to the compiler (%s)" % env["OMPI_CC"])

if "CUDA" in args:
   opts_list += ' -DCUDA_TOOLKIT_ROOT_DIR="/opt/cuda_%s" '%(args["CUDA"],)

if not args["host"].lower().find("win")>-1:
   call_opts = {"executable":"/bin/bash"}
else:
   opts_list += '-G "NMake Makefiles JOM" -DBUILD_SHARED_LIBS=on '
   build_cmd = "jom -j4"

if args["host"].lower().find("mac")>-1:
   env["CMAKE_PREFIX_PATH"] = "/opt/local"

#construct string for all "GMX_" variables
opts_list += " ".join(["-D%s=%s"%(k,v) for k,v in opts.iteritems()])
opts_list += " -DGMX_DEFAULT_SUFFIX=off ."

if "CMAKE_BUILD_TYPE" in args:
   opts_list += " -DCMAKE_BUILD_TYPE=" + args["CMAKE_BUILD_TYPE"]
else:
   opts_list += " -DCMAKE_BUILD_TYPE=Debug"

def call_cmd(cmd):
   print "Running " + cmd
   return subprocess.call(cmd, stdout=sys.stdout, stderr=sys.stderr, shell=True, **call_opts)

# Set up a dictionary to map repositories to the refspec we want from
# them.
refspecs={"gromacs": env['GROMACS_REFSPEC'],
          "regressiontests": env['REGRESSIONTESTS_REFSPEC'],
          "releng": "refs/heads/4.6.0"}
# Over-ride the refspec for the project that we're actually testing
# with the refspec we want to test from it.
refspecs[env['GERRIT_PROJECT']]=env['GERRIT_REFSPEC']
# Prepare to set up a dictionary that will hold the correct SHA for
# each refspec in its remote repo, so we can check we're testing the
# right combination of refspecs.
correct_sha={}

# Make a directory into which we can check out the desired refspec.
def checkout_project(project):
   if not os.path.exists(project): os.makedirs(project)
   os.chdir(project)
   cmd = 'git init && git fetch git://git.gromacs.org/%s.git %s && git checkout -q -f FETCH_HEAD && git clean -fdxq' % (project,refspecs[project])
   if call_cmd(cmd)!=0:
      sys.exit("Download FAILED")
   call_cmd("git gc")
   os.chdir("..")

for project in sorted(refspecs.keys()):
   # Check out the project(s) that are not currently under test
   if env['GERRIT_PROJECT']!=project and 'releng'!=project:
      checkout_project(project)

   # Query the remote repo for the SHA that should be used for this test
   cmd = 'git ls-remote git://git.gromacs.org/%s.git %s' % (project,refspecs[project])
   p = subprocess.Popen(cmd,stdout=subprocess.PIPE,shell=True,cwd=project)
   correct_sha[project] = p.communicate()[0].strip()
   if p.returncode != 0:
      sys.exit("The subprocess that ran '%s' failed. This means the SHA of that HEAD is unknown, so we cannot be sure the previous checkout was of the correct content for this test." % cmd)

env['PATH']=os.pathsep.join([env['PATH']]+map(os.path.abspath,["gromacs/src/kernel","gromacs/src/tools","gromacs/src/mdlib","gromacs/src/gmxlib"]))

print "-----------------------------------------------------------"
print "Building using versions:"
wrong_version=0
for project in sorted(refspecs.keys()):
   # What version of this project is checked out?
   cmd = "git rev-parse HEAD"
   p = subprocess.Popen(cmd,stdout=subprocess.PIPE,shell=True,cwd=project)
   head_version = p.communicate()[0].strip()
   if p.returncode != 0:
      sys.exit("The subprocess that ran '%s' failed. So we cannot determine the SHA of this HEAD!" % cmd)

   # Tell the user what we're doing with this project
   print "%-20s %-30s %s"%(project + ":", refspecs[project],head_version)

   # Is the version checked out OK?
   if not correct_sha[project].startswith(head_version):
      print "Checkout of refspec %s from project %s did not succeed. In the remote repo it is %7s, but somehow the local repo is %7s." % (refspecs[project], project, correct_sha[project], head_version)
      wrong_version += 1
print "-----------------------------------------------------------"

if 0 < wrong_version:
   sys.exit("Failed to check out correct project(s)")

os.chdir("gromacs")   
cmd = "%s && cmake --version && cmake %s && %s && %s" % (env_cmd,opts_list,build_cmd,test_cmd)

if call_cmd(cmd)!=0:
   sys.exit("Build FAILED")

os.chdir("../regressiontests")
cmd = '%s && perl gmxtest.pl -mpirun mpirun -xml -nosuffix all' % (env_cmd,)
if use_asan:
   cmd+=' -parse asan_symbolize.py'

# setting this stuff below is just a temporary solution,
# it should all be passed as a proper the runconf from outside

# OpenMP should always work when compiled in!
if "GMX_OPENMP" in opts.keys() and cmake_istrue(opts["GMX_OPENMP"]):
   cmd += " -ntomp 2"

mdparam = ""
if use_gpu:
   if use_mpi or use_tmpi:
      mdparam+=" -gpu_id 12"  # for (T)MPI use the two GT 640-s
   else:
      mdparam+=" -gpu_id 0"   # use GPU #0 by default

if args["host"].lower().find("win")>-1:
   env['PATH']+=';C:\\strawberry\\perl\\bin'

if use_mpi:
   cmd += ' -np 2'
elif use_tmpi:
   mdparam += ' -ntmpi 2'
if "GMX_DOUBLE" in opts.keys() and cmake_istrue(opts["GMX_DOUBLE"]):
   cmd += ' -double'
cmd += ' -mdparam "%s"'%(mdparam,)
if call_cmd(cmd)!=0:
   sys.exit("Regression tests failed")


