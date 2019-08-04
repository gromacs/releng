"""
Information about Jenkins build agents
"""
from common import ConfigurationError

BS_MAC = 'bs_mac'
BS_MIC = 'bs_mic'
BS_NIX1204 = 'bs_nix1204'
BS_NIX1310 = 'bs_nix1310'
BS_NIX1404 = 'bs_nix1404'
BS_NIX_AMD_GPU = 'bs_nix-amd_gpu'
BS_NIX_AMD = 'bs_nix-amd'
BS_GPU01 = 'bs_gpu01'
BS_NIX_DOCS = 'bs_nix-docs'
BS_NIX_STATIC_ANALYZER = 'bs_nix-static_analyzer'
BS_WIN2008 = 'bs_Win2008_64'
BS_WIN2012R2 = 'bs-win2012r2'
BS_JETSON_TK1 = 'bs_jetson_tk1'
BS_JETSON_TX1 = 'bs_jetson_tx1'
BS_OVERDRIVE_1000 = 'bs_overdrive_1000'

DOCKER_DEFAULT = 'docker-ubuntu-15.04'

ALL_LABELS = (DOCKER_DEFAULT,)

# For each agent that releng-based dynamic matrix builds should be able to run
# builds on, this should list the labels that the agent supports (see
# options.py and docs/releng.rst for general information about the labels).
#
# If we later move to a workflow build, we can skip all this, and directly use
# the labels assigned to agents in Jenkins: the workflow plugin supports
# selecting the node using a label expression, which we can easily construct
# directly in options.py.
#
# Versions that are commented out are installed and working, but are not
# part of the description, as a crude form of load balancing.
_HOST_LABELS = {
            BS_MIC:         { 'gcc-4.8', 'gcc-4.9', 'gcc-5', 'gcc-7', 'gcc-8', 'gcc-9',
                              # These CUDA versions are installed, but aren't useful to use
                              # 'cuda-6.5', 'cuda-7.5',
                              # CUDA is made available on this agent only so that we
                              # can test that a CUDA build on a agent with no GPU works.
                              'cuda-7.0', 'cuda-10.0', 'cuda-10.1',
                              'icc-16.0', 'icc-16', 'icc-17', 'icc-18', 'icc-19',
                              'phi',
                              'cmake-2.8.12.2', 'cmake-3.3.2', 'cmake-3.6.1', 'cmake-3.8.1', 'cmake-3.9.6', 'cmake-3.10.0',
                              'sse2', 'sse4.1', 'avx_256', 'mic',
                              'tsan', 'x11'
                            },
            BS_MAC:         { 'gcc-4.8', 'gcc-4.9', 'gcc-6', 'gcc-8',
                              'clang-4', 'clang-6', 'clang-7', 'clang-8',
                              'gcov-4.6', 'gcov-6.1', 'gcov-6',
                              'icc-12.1', 'icc-13.0', 'icc-15.0', 'icc-16.0', 'icc-16',
                              'cmake-3.4.3', 'cmake-3.5.2', 'cmake-3.12.1',
                              'sse2', 'sse4.1',
                              'tidy',
                              # 'x11',
                              },
            BS_NIX1204:     { 'gcc-4.8', 'gcc-5', 'gcc-7', 'gcc-8',
                              # These gcc are installed, but we don't want to use them if we can avoid it.
                              # 'gcc-6',
                              'clang-4', 'clang-5',
                              # These clang are installed, but we don't want to use them if we can avoid it.
                              # 'clang-6',
                              'cuda-6.5', 'cuda-7.0', 'cuda-8.0', 'cuda-9.1', 'cuda-9.2', 'cuda-10.0', 'cuda-10.1',
                              'opencl-1.1', 'opencl-1.2',
                              # These are installed, but we prefer to target such jobs to bs_nix1310
                              # 'cuda-9.0',
                              'nvidia', # GPU vendor
                              'cmake-2.8.8', 'cmake-3.6.1', 'cmake-3.10.0', 'cmake-3.15.1', # 'cmake-3.8.1', 'cmake-3.9.6',
                              'sse2', 'sse4.1', 'avx_256', 'avx2_256',
                              'libhwloc-1.8', 'libhwloc-2.0.4',
                              'mpi', # 'x11',
                              'valgrind' },
            BS_NIX1310:     { 'gcc-4.8', 'gcc-4.9', 'gcc-5', 'gcc-6',
                              'clang-6',
                              # These clang are installed, but we don't want to use them if we can avoid it.
                              # 'clang-3.4', 'clang-4', 'clang-5',
                              'icc-18', 'icc-19',
                              'cuda-5.0', 'cuda-7.0', 'cuda-7.5', 'cuda-8.0', 'cuda-9.0',
                              'opencl-1.1', 'opencl-1.2',
                              'clFFT-2.14',
                              'nvidia', # GPU vendor
                              'cmake-2.8.11.2', 'cmake-3.4.3', 'cmake-3.5.2', 'cmake-3.8.1',  'cmake-3.9.6', #'cmake-3.10.0',
                              'sse2', 'sse4.1', 'avx_256', 'avx2_256',
                              'mpi', # 'x11',
                              'valgrind', 'tsan',
                              'libhwloc-1.7',
                            },
            BS_NIX1404:     { 'gcc-7', 'gcc-8',
                              'clang-7',
                              'cmake-3.4.3', 'cmake-3.9.6', 'cmake-3.13.2',
                              'sse2', 'sse4.1', 'avx_128_fma',
                              'mpi',
                              'valgrind'
                            },
            BS_NIX_AMD_GPU: { 'gcc-4.8', 'gcc-4.9', 'gcc-5', 'gcc-8',
                              'amdappsdk-3.0',
                              'opencl-1.1', 'opencl-1.2', 'opencl-2.0',
                              'cmake-2.8.12.2', 'cmake-3.5.2',
                              'sse2', 'sse4.1', 'avx_128_fma',
                              'mpi',
                            },
            BS_NIX_AMD:     { 'gcc-4.8', 'gcc-4.9', 'gcc-5',
                              'clang-3.4', 'clang-3.6', 'clang-4', 'clang-5', 'clang-6', 'clang-7',
                              'cmake-2.8.12.2', 'cmake-3.4.3', 'cmake-3.11.4',
                              'sse2', 'sse4.1', 'avx_128_fma',
                              'mpi',
                            },
            BS_GPU01:       { 'gcc-5', 'gcc-7', 'gcc-8', 'gcc-9',
                              'clang-4', 'clang-5', 'clang-6', 'clang-7',
                              'libcxx-7',
                              'cmake-3.4.3', 'cmake-3.12.1', 'cmake-3.14.5',
                              'sse2', 'sse4.1', 'avx_256', 'avx2_256',
                              'mpi',
                              'opencl-1.1', 'opencl-1.2', 'opencl-2.0',
                              'clFFT-2.14',
                              'amd', # GPU vendor
                              'tsan',
                              'amdappsdk-3.0', # TODO: remove
                              'libhwloc-1.11.2',
                            },
            BS_NIX_DOCS:    { 'cmake-3.6.1', 'cmake-3.13.3',
                              'doxygen-1.8.5', 'sphinx-1.6.1'
                            },
            BS_NIX_STATIC_ANALYZER: {
                              'clang-3.8', 'clang-4', 'clang-5', 'clang-6', 'clang-7',
                              'clang-static-analyzer-3.8', 'clang-static-analyzer-4', 'clang-static-analyzer-5',
                              'clang-static-analyzer-6', 'clang-static-analyzer-7',
                              'cmake-3.5.1', 'cmake-3.7.2', 'cmake-3.12.4'
                            },
            BS_WIN2008:     { 'msvc-2010',
                              'icc-12.1' },
            BS_WIN2012R2:   { 'msvc-2013', 'msvc-2015', 'msvc-2017',
                              'icc-16.0', 'icc-16', 'icc-18',
                              'cmake-2.8.12.2', 'cmake-3.2.3', 'cmake-3.3.0', 'cmake-3.6.1', 'cmake-3.10.2',
                              'sse2', 'sse4.1', 'avx_256', 'avx2_256',
                            },
            BS_JETSON_TK1:  { 'gcc-4.8', 'gcc-4.9', 'gcc-5',
                              'clang-3.9',
                              'arm_neon',
                              'cmake-3.8.1', 'cmake-3.13.3',
                              'cuda-6.5',
                              'nvidia', # GPU vendor
                             },
            BS_JETSON_TX1:  { 'gcc-4.8', 'gcc-4.9', 'gcc-5',
                              'clang-3.9',
                              'arm_neon_asimd',
                              'cmake-3.5.1', 'cmake-3.13.3',
                              'cuda-8.0'
                              'nvidia', # GPU vendor
                              },
            BS_OVERDRIVE_1000: {
                                 'armclang-18.3', 'armclang-18.4',  'gcc-7',
                                 # ARMPL comes with the ARM HPC stack, so no separate versioning
                                 'armpl',
                                 'arm_neon_asimd',
                                 'cmake-3.10.2',
                                 'armhpc-18.3', 'armhpc-18.4' },
            DOCKER_DEFAULT: {} # TODO
        }

# Specifies an installed gcc (ie found in the list above) for each
# host that should be used for compilers (ie icc and clang) that need
# to use an external C++ standard library, such as one from gcc.
_DEFAULT_GCC_FOR_LIBSTDCXX = {
            # This agent uses macports clang that does not need a gcc
            # BS_MAC: 'gcc-6',
            BS_MIC: 'gcc-5',
            BS_NIX1204: 'gcc-5',
            BS_NIX1310: 'gcc-5',
            BS_NIX1404: 'gcc-7',
            BS_NIX_AMD_GPU: 'gcc-5',
            BS_GPU01: 'gcc-5',
            BS_NIX_AMD: 'gcc-5',
            BS_JETSON_TK1: 'gcc-5',
            BS_JETSON_TX1: 'gcc-5',
            BS_OVERDRIVE_1000: 'gcc-7'
    }

def get_default_gcc_for_libstdcxx(host):
    return _DEFAULT_GCC_FOR_LIBSTDCXX.get(host, None)

# Specifies a shell-like command that establishes an enviroment that should
# be used on particular hosts in order to access a suitable toolchain.
# TODO This could be implemented as "agent" BS_MIC_DEVTOOLSET_4, or similar.
_ENVIRONMENT_SUBSHELL = {
            # Centos 6.9 on bs_mic uses ancient gcc and ld
            BS_MIC: '/usr/bin/scl enable devtoolset-4'
    }

def get_environment_subshell(host):
    # The default system toolchains are mostly fine for us to use.
    return _ENVIRONMENT_SUBSHELL.get(host, None)

# Specifies the set of hosts that are allowed to execute matrix configurations.
# This should match the nodes selected on the node axis in the Jenkins matrix jobs.
# If any config gets assigned to a node outside the Jenkins matrix job axis, Jenkins
# would silently not build it. This list is used to check the matrix config, so
# we give a fatal error rather than silently omit a build.
_MATRIX_HOSTS = {
            BS_MAC,
            BS_MIC,
            BS_NIX1204,
            BS_NIX1310,
            BS_NIX1404,
            BS_NIX_AMD_GPU,
            BS_NIX_AMD,
            BS_GPU01,
            BS_JETSON_TK1,
            BS_JETSON_TX1,
            BS_OVERDRIVE_1000,
            BS_WIN2012R2
        }

# Specifies groups of hosts that should only be used if no host outside the
# group can be used.  For example, use Windows machines only for builds that
# can only be run there.
#
# Order matters; the first set is excluded first from the set of possible
# hosts, so that if a build can run in the first or second set, it will run in
# the second.
_SPECIAL_HOST_GROUPS = [
            # Windows
            {BS_WIN2008, BS_WIN2012R2},
            # Special-purpose VMs
            {BS_NIX_STATIC_ANALYZER},
            {BS_NIX_DOCS},
            # ARM agents
            {BS_JETSON_TK1, BS_JETSON_TX1, BS_OVERDRIVE_1000},
            # GPU agents
            {BS_GPU01, BS_NIX1204, BS_NIX1310},
            # Deprecated GPU agents
            {BS_NIX_AMD_GPU}
        ]

# For hosts not specifically listed here, a default hard-coded in
# get_default_build_parallelism() is used.
_DEFAULT_BUILD_PARALLELISM = {
            BS_WIN2008: 4,
            # The following agents are limited to a single executor, so we
            # should use all the hardware threads
            BS_JETSON_TK1: 4,
            BS_JETSON_TX1: 4,
            BS_OVERDRIVE_1000: 4,
            BS_NIX_AMD_GPU: 4,
            # 8 physical cores without HT, 2 executors
            BS_MAC: 4,
            # 8 VM cores
            BS_NIX_STATIC_ANALYZER: 8,
            # 8 cores with HT, 2 executors
            BS_GPU01: 8,
            # 4 physical cores, each with 2 hyperthreads
            BS_WIN2012R2: 8
        }

def is_label(host):
    return host in ALL_LABELS

def is_matrix_host(host):
    return host in _MATRIX_HOSTS

def get_default_build_parallelism(host):
    return _DEFAULT_BUILD_PARALLELISM.get(host, 2)

def pick_host(labels, opts):
    """Selects a host that can build with a given set of labels."""
    if labels.issubset(_HOST_LABELS[DOCKER_DEFAULT]):
        return DOCKER_DEFAULT
    possible_hosts = []
    for host, host_labels in _HOST_LABELS.iteritems():
        if labels.issubset(host_labels):
            possible_hosts.append(host)
    if not possible_hosts:
        return None
    # TODO: If there are multiple possible hosts, it would be better to
    # optimize the selection globally over all the configurations to
    # avoid assigning all the builds to the same host.
    for group in _SPECIAL_HOST_GROUPS:
        if set(possible_hosts).issubset(group):
            return possible_hosts[0]
        possible_hosts = [x for x in possible_hosts if x not in group]
    return possible_hosts[0]
