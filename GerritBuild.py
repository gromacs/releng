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
call_opts = {}
opts_list = ""
ctest = "ctest"
    
if "CMakeVersion" in args:
   env["PATH"] =  "%s/tools/cmake-%s/bin:%s" % (env["HOME"],args["CMakeVersion"],env["PATH"])
   ctest = "/usr/bin/ctest"  #problem with older versions

if not 'Compiler' in args or not 'CompilerVersion' in args:
   error("Compiler and CompilerVersion needs to be specified")

if not os.getenv("NODE_NAME"):
   error("Jenkins did not set NODE_NAME environment variable")
else:
   print "Node name: " + os.getenv("NODE_NAME")

if args['Compiler']=="gcc":
   env["CC"]  = "gcc-"      + args["CompilerVersion"]
   env["CXX"] = "g++-"      + args["CompilerVersion"]
   env["FC"]  = "gfortran-" + args["CompilerVersion"]
   if 'CMAKE_BUILD_TYPE' in args and args["CMAKE_BUILD_TYPE"]=="TSAN":
      env["LD_LIBRARY_PATH"] =  "%s/tools/gcc-nofutex/lib64" % env["HOME"]

if args['Compiler']=="clang":
   env["CC"]  = "clang-"    + args["CompilerVersion"]
   env["CXX"] = "clang++-"  + args["CompilerVersion"]

if args['Compiler']=="icc":
   if os.getenv("NODE_NAME").lower().find("win")>-1:
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

use_gpu = use_mpi = use_tmpi = use_separate_pme_nodes = False
if "GMX_GPU" in opts.keys() and cmake_istrue(opts["GMX_GPU"]):
   use_gpu = True
if "GMX_MPI" in opts.keys() and cmake_istrue(opts["GMX_MPI"]):
   use_mpi = True
if not use_mpi and (not "GMX_THREAD_MPI" in opts.keys() or cmake_istrue(opts["GMX_THREAD_MPI"])):
   use_tmpi = True
if "GMX_TEST_NPME" in opts.keys() and (use_mpi or use_tmpi):
   use_separate_pme_nodes = True

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

if not os.getenv("NODE_NAME").lower().find("win")>-1:
   call_opts = {"executable":"/bin/bash"}
   env['PATH']+=":%s/bin"%env['HOME']
else:
   opts_list += '-G "NMake Makefiles JOM" '
   build_cmd = "jom -j4"

# If we are doing an mdrun-only build, then we cannot run the
# regression tests at all, so set up a flag to do the right thing
do_regressiontests = not ("GMX_BUILD_MDRUN_ONLY" in args and args["GMX_BUILD_MDRUN_ONLY"]=="ON")

#Disable valgrind for Windows (not supported), Mac+ICC (too many false positives), ASAN, TSAN, Release
use_valgrind = not os.getenv("NODE_NAME").lower().find("win")>-1 and not (os.getenv("NODE_NAME").lower().find("mac")>-1 and args['Compiler']=="icc")
use_valgrind = use_valgrind and not ("CMAKE_BUILD_TYPE" in args and args["CMAKE_BUILD_TYPE"]!="Debug")
if use_valgrind:
   test_cmds = ["ctest -D ExperimentalTest -LE GTest -V",
                "%s -D ExperimentalMemCheck -L GTest -V"%(ctest,),
                "xsltproc -o Testing/Temporary/valgrind_unit.xml ../releng/ctest_valgrind_to_junit.xsl  Testing/`head -n1 Testing/TAG`/DynamicAnalysis.xml"]
else:
   test_cmds = ["ctest -D ExperimentalTest -V"]

if os.getenv("NODE_NAME").lower().find("mac")>-1:
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
          "releng": "refs/heads/5.0.0"}
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
   cmd = 'git init && git fetch ssh://jenkins@gerrit.gromacs.org/%s.git %s && git checkout -q -f FETCH_HEAD && git clean -ffdxq' % (project,refspecs[project])
   if call_cmd(cmd)!=0:
      sys.exit("Download FAILED")
   call_cmd("git gc")
   os.chdir("..")

for project in sorted(refspecs.keys()):
   # Check out the project(s) that are not currently under test
   if env['GERRIT_PROJECT']!=project and 'releng'!=project:
      checkout_project(project)

   # Query the remote repo for the SHA that should be used for this test
   cmd = 'git ls-remote ssh://jenkins@gerrit.gromacs.org/%s.git %s' % (project,refspecs[project])
   p = subprocess.Popen(cmd,stdout=subprocess.PIPE,shell=True,cwd=project)
   correct_sha[project] = p.communicate()[0].strip()
   if p.returncode != 0:
      sys.exit("The subprocess that ran '%s' failed. This means the SHA of that HEAD is unknown, so we cannot be sure the previous checkout was of the correct content for this test." % cmd)

env['PATH']=os.pathsep.join([env['PATH']]+map(os.path.abspath,["gromacs/bin"]))

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
os.environ["GMX_NO_TERM"]="1" #disable Term signal handler. Helps Jenkins aborts jobs.

cmd = "%s && cmake --version && cmake %s && %s && %s tests" % (env_cmd,opts_list,build_cmd,build_cmd)
if call_cmd(cmd)!=0:
   sys.exit("Build FAILED")

for i in test_cmds:
   if call_cmd("%s && %s"%(env_cmd,i)) != 0:
      print "+++ TEST FAILED +++" #used with TextFinder

os.chdir("../regressiontests")
cmd = '%s && perl gmxtest.pl -mpirun mpirun -xml -nosuffix all' % (env_cmd,)
if 'CMAKE_BUILD_TYPE' in args and args["CMAKE_BUILD_TYPE"]=="ASAN" and args['Compiler']=="clang":
   cmd+=' -parse asan_symbolize.py'

# setting this stuff below is just a temporary solution,
# it should all be passed as a proper the runconf from outside

# OpenMP should always work when compiled in!
if "GMX_OPENMP" in opts.keys() and cmake_istrue(opts["GMX_OPENMP"]):
   cmd += " -ntomp 2"

mdparam = ""
if use_gpu:
   # We used to pass -gpu_id in gmxtest.pl -mdparam to add to the
   # mdrun command line, but this does not interact well with the
   # gmxtest.pl test harness needing to handle test cases that must
   # run with only one rank.
   if use_mpi or use_tmpi:
      gpu_id = "12" # for (T)MPI use the two GT 640-s
   else:
      gpu_id = "0" # use GPU #0 by default
   cmd += ' -gpu_id %s' % (gpu_id)

if os.getenv("NODE_NAME").lower().find("win")>-1:
   env['PATH']+=';C:\\strawberry\\perl\\bin'

if use_separate_pme_nodes:
   # mdrun -npme only works with > 2 ranks
   if use_mpi:
      cmd += ' -np 3'
   if use_tmpi:
      cmd += ' -nt 3'
   if use_gpu:
      gpu_id = "121" # gmxtest.pl trims this if there is a separate PME node actually in use
   cmd += ' -npme 1'
elif use_mpi:
   cmd += ' -np 2'
elif use_tmpi:
   cmd += ' -nt 2'
if "GMX_DOUBLE" in opts.keys() and cmake_istrue(opts["GMX_DOUBLE"]):
   cmd += ' -double'
cmd += ' -mdparam "%s"'%(mdparam,)
if do_regressiontests:
   if call_cmd(cmd)!=0:
      sys.exit("Regression tests failed")
