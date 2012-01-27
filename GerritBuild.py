import sys,subprocess
from os import environ as env

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

if "Compiler" in args and args['Compiler']=="gcc" and "CompilerVersion" in args:
   env["CC"]  = "gcc-"      + args["CompilerVersion"]
   env["CXX"] = "g++-"      + args["CompilerVersion"]
   env["FC"]  = "gfortran-" + args["CompilerVersion"] 

if "Compiler" in args and args['Compiler']=="icc":
   env["CC"]  = "icc"
   env["CXX"] = "icpc"
   env_cmd = ". /opt/intel/bin/iccvars.sh intel64"
   opts_list += '-DGMX_FFT_LIBRARY=mkl  -DMKL_LIBRARIES="${MKLROOT}/lib/intel64/libmkl_intel_lp64.so;${MKLROOT}/lib/intel64/libmkl_sequential.so;${MKLROOT}/lib/intel64/libmkl_core.so" -DMKL_INCLUDE_DIR=${MKLROOT}/include'

if "GMX_EXTERNAL" in opts.keys():
    v = opts.pop("GMX_EXTERNAL")
    opts["GMX_EXTERNAL_LAPACK"] = v
    opts["GMX_EXTERNAL_BLAS"] = v
    env["CMAKE_LIBRARY_PATH"] = "/usr/lib/atlas-base"

if "host" in args and args["host"].lower().find("win")>-1:
    env_cmd = "SetEnv /Release"
    build_cmd = "msbuild /m:2 /p:Configuration=MinSizeRel All_Build.vcxproj"
    opts_list += '-G "Visual Studio 10 Win64" '
else:
   call_opts = {"executable":"/bin/bash"}

#construct string for all "GMX_" variables
opts_list += " ".join(["-D%s=%s"%(k,v) for k,v in opts.iteritems()])
opts_list += " -DGMX_DEFAULT_SUFFIX=off -DCMAKE_BUILD_TYPE=Debug ."

cmd = "%s && cmake --version && cmake %s && %s && %s" % (env_cmd,opts_list,build_cmd,test_cmd)

print "Running " + cmd

ret = subprocess.call(cmd, stdout=sys.stdout, stderr=sys.stderr, shell=True, **call_opts)
sys.exit(ret)


