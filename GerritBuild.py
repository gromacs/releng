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
call_opts = {}
opts_list = ""
ctest = "ctest"
    
if "CMakeVersion" in args:
   env["PATH"] =  "%s/tools/cmake-%s/bin:%s" % (env["HOME"],args["CMakeVersion"],env["PATH"])
   ctest = "/usr/bin/ctest"  #problem with older versions

if not 'Compiler' in args or not 'CompilerVersion' in args or not 'host' in args:
   error("Compiler, CompilerVersion and host needs to be specified")

if args['Compiler']=="gcc":
   env["CC"]  = "gcc-"      + args["CompilerVersion"]
   env["CXX"] = "g++-"      + args["CompilerVersion"]
   env["FC"]  = "gfortran-" + args["CompilerVersion"]

if args['Compiler']=="clang":
   env["CC"]  = "clang-"    + args["CompilerVersion"]
   env["CXX"] = "clang++-"  + args["CompilerVersion"]
   if args["CompilerVersion"]=="3.2":
      #bit ugly to hard code this here but way to long to pass all from Jenkins
      opts_list += '-DCMAKE_C_FLAGS_DEBUG="-g -O1 -faddress-sanitizer" -DCMAKE_CXX_FLAGS_DEBUG="-g -O1 -faddress-sanitizer" -DCMAKE_EXE_LINKER_FLAGS_DEBUG=-faddress-sanitizer -DCUDA_PROPAGATE_HOST_FLAGS=no '
      opts_list += '-DBUILD_SHARED_LIBS=no ' #http://code.google.com/p/address-sanitizer/issues/detail?id=38

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

if "GMX_MPI" in opts.keys() and cmake_istrue(opts["GMX_MPI"]):
   if "CompilerVersion" in args:
      env["OMPI_CC"] =env["CC"]
      env["OMPI_CXX"]=env["CXX"]
      if "FC" in env:
         env["OMPI_FC"] =env["FC"]
   env["CC"] ="mpicc"
   env["CXX"]="mpic++"
   env["FC"] ="mpif90"

if "CUDA" in args:
   opts_list += '-D CUDA_TOOLKIT_ROOT_DIR="/opt/cuda_%s" '%(args["CUDA"],)

if not args["host"].lower().find("win")>-1:
   call_opts = {"executable":"/bin/bash"}
else:
   opts_list += '-G "NMake Makefiles JOM" '
   build_cmd = "jom -j4"

#Disable valgrind for Windows (not supported), Mac+ICC (not many false positives), Clang 3.2 (santizer is used instead)
if not args["host"].lower().find("win")>-1 and not (args["host"].lower().find("mac")>-1 and args['Compiler']=="icc") and not (args['Compiler']=="clang" and args["CompilerVersion"]=="3.2"):
   test_cmds = ["ctest -D ExperimentalTest -LE GTest -V",
                "%s -D ExperimentalMemCheck -L GTest -V"%(ctest,),
                "xsltproc -o Testing/Temporary/valgrind_unit.xml ../releng/ctest_valgrind_to_junit.xsl  Testing/`head -n1 Testing/TAG`/DynamicAnalysis.xml"]
else:
   test_cmds = ["ctest -D ExperimentalTest -V"]

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

def checkout_project(project,refname):
   if not os.path.exists(project): os.makedirs(project)
   os.chdir(project)
   if env['GERRIT_PROJECT']!=project:
      cmd = 'git init && git fetch git://git.gromacs.org/%s.git %s && git checkout -q -f FETCH_HEAD && git clean -fdxq'%(project,env[refname])
      print "Running " + cmd
      if call_cmd(cmd)!=0:
         sys.exit("Download FAILED")
      call_cmd("git gc")

checkout_project("gromacs",'GROMACS_REFSPEC')

cmd = "%s && cmake --version && cmake %s && %s" % (env_cmd,opts_list,build_cmd)
   

if call_cmd(cmd)!=0:
   sys.exit("Build FAILED")

for i in test_cmds:
   if call_cmd("%s && %s"%(env_cmd,i)) != 0:
      print "+++ TEST FAILED +++" #used with TextFinder

os.chdir("..")
checkout_project("regressiontests", 'REGRESSIONTESTS_REFSPEC')

cmd = '%s && perl gmxtest.pl -mpirun mpirun -xml -nosuffix all' % (env_cmd,)
if args["host"].lower().find("win")>-1: 
   env['PATH']+=';C:\\strawberry\\perl\\bin'
env['PATH']=os.pathsep.join([env['PATH'],os.path.abspath("../gromacs/bin")])
if "GMX_MPI" in opts.keys() and cmake_istrue(opts["GMX_MPI"]):
   cmd += ' -np 2'
if "GMX_DOUBLE" in opts.keys() and cmake_istrue(opts["GMX_DOUBLE"]):
   cmd += ' -double'
if call_cmd(cmd)!=0:
   sys.exit("Regression tests failed")


