"""
Information about Jenkins build slaves
"""
from common import ConfigurationError

BS_MAC = 'bs_mac'
BS_MIC = 'bs_mic'
BS_NIX1204 = 'bs_nix1204'
BS_NIX1310 = 'bs_nix1310'
BS_NIX1404 = 'bs_nix1404'
BS_NIX_AMD_GPU = 'bs_nix-amd_gpu'
BS_NIX_AMD = 'bs_nix-amd'
BS_NIX_DOCS = 'bs_nix-docs'
BS_NIX_STATIC_ANALYZER = 'bs_nix-static_analyzer'
BS_WIN2008 = 'bs_Win2008_64'
BS_WIN2012R2 = 'bs-win2012r2'

DOCKER_DEFAULT = 'docker-ubuntu-15.04'

ALL_LABELS = (DOCKER_DEFAULT,)

# For each slave that releng-based dynamic matrix builds should be able to run
# builds on, this should list the labels that the slave supports (see
# options.py and docs/releng.rst for general information about the labels).
#
# If we later move to a workflow build, we can skip all this, and directly use
# the labels assigned to slaves in Jenkins: the workflow plugin supports
# selecting the node using a label expression, which we can easily construct
# directly in options.py.
#
# Versions that are commented out are installed and working, but are not
# part of the description, as a crude form of load balancing.
#
# TODO Remove the "gcc-[56].?" and "clang-4.0" labels once the test
# matrix specifications in the source repos have all been updated to
# follow the new style in Redmine #2161.
_HOST_LABELS = {
            BS_MIC:         { 'gcc-4.4', 'gcc-4.7', 'gcc-4.8', 'gcc-4.9', 'gcc-5.2', 'gcc-5',
                              # These CUDA versions are installed, but aren't useful to use
                              # 'cuda-6.5', 'cuda-7.0', 'cuda-7.5',
                              'icc-14.0', 'icc-15.0', 'icc-16.0',
                              'phi',
                              'cmake-2.8.12.2', 'cmake-3.3.2', 'cmake-3.6.1', 'cmake-3.8.1',
                              'sse2', 'sse4.1', 'avx_256', 'mic' },
            BS_MAC:         { 'gcc-4.2', 'gcc-4.4', 'gcc-4.5', 'gcc-4.6', 'gcc-4.7', 'gcc-4.8', 'gcc-4.9', 'gcc-6.1', 'gcc-6',
                              'clang-4.0', 'clang-4',
                              'gcov-4.6', 'gcov-6.1', 'gcov-6',
                              'icc-12.1', 'icc-13.0', 'icc-15.0', 'icc-16.0',
                              'cmake-3.4.3', 'cmake-3.5.2',
                              'sse2', 'sse4.1',
                              'x11' },
            BS_NIX1204:     { 'gcc-4.4', 'gcc-4.5', 'gcc-4.6', 'gcc-4.7', 'gcc-4.8', 'gcc-5.4', 'gcc-5',
                              'clang-3.3',
                              'cuda-5.0', 'cuda-5.5', 'cuda-6.0', 'cuda-6.5', 'cuda-7.0', 'cuda-8.0',
                              'cmake-2.8.8', 'cmake-3.6.1',# 'cmake-3.8.1',
                              'sse2', 'sse4.1', 'avx_256', 'avx2_256',
                              'mpi', 'x11',
                              'valgrind' },
            BS_NIX1310:     { 'gcc-4.4', 'gcc-4.6', 'gcc-4.7', 'gcc-4.8', 'gcc-4.9',
                              # This clang is installed, but we don't want to use it if we can avoid it.
                              # 'clang-3.4',
                              'clang-4',
                              # These are installed, but have no active license.
                              # 'icc-15.0', 'icc-16.0',
                              'cuda-5.0', 'cuda-5.5', 'cuda-6.0', 'cuda-6.5', 'cuda-7.0', 'cuda-7.5', 'cuda-8.0',
                              'cmake-2.8.11.2', 'cmake-3.4.3', 'cmake-3.5.2', 'cmake-3.8.1',
                              'sse2', 'sse4.1', 'avx_256', 'avx2_256',
                              'mpi', 'x11',
                              'valgrind', 'tsan' },
            BS_NIX1404:     { 'gcc-4.4', 'gcc-4.6', 'gcc-4.7', 'gcc-4.8', 'gcc-4.9', 'gcc-5.1', 'gcc-5', 'gcc-7',
                              'clang-3.5', 'clang-3.6', 'clang-3.7', 'clang-3.8', 'clang-3.9',
                              # These CUDA versions are installed, but aren't useful to use
                              # 'cuda-6.0', 'cuda-6.5', 'cuda-7.0',
                              'cmake-2.8.12.2', 'cmake-3.0.2', 'cmake-3.4.3',
                              'sse2', 'sse4.1', 'avx_128_fma',
                              'mpi',
                              'valgrind', 'msan' },
            BS_NIX_AMD_GPU: { 'gcc-4.4', 'gcc-4.6', 'gcc-4.7', 'gcc-4.8', 'gcc-4.9', 'gcc-5.2', 'gcc-5',
                              'amdappsdk-3.0',
                              'cmake-2.8.12.2', 'cmake-3.5.2',
                              'sse2', 'sse4.1', 'avx_128_fma',
                              'mpi' },
            BS_NIX_AMD:     { 'gcc-4.4', 'gcc-4.6', 'gcc-4.7', 'gcc-4.8', 'gcc-4.9', 'gcc-5.2', 'gcc-5',
                              'clang-3.4', 'clang-4',
                              'cmake-2.8.12.2', 'cmake-3.4.3',
                              'sse2', 'sse4.1', 'avx_128_fma',
                              'mpi' },
            BS_NIX_DOCS:    { 'cmake-3.6.1'
                            },
            BS_NIX_STATIC_ANALYZER: {
                              'clang-3.8', 'clang-4',
                              'clang-static-analyzer-3.8', 'clang-static-analyzer-4',
                              'cmake-3.5.1', 'cmake-3.7.2'
                            },
            BS_WIN2008:     { 'msvc-2010',
                              'icc-12.1' },
            BS_WIN2012R2:   { 'msvc-2013', 'msvc-2015',
                              'icc-16.0',
                              'cmake-2.8.12.2', 'cmake-3.2.3', 'cmake-3.3.0', 'cmake-3.6.1' },
            DOCKER_DEFAULT: {} # TODO
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
            # GPU slaves
            {BS_NIX_AMD_GPU, BS_NIX1204, BS_NIX1310}
        ]

def is_label(host):
    return host in ALL_LABELS

def pick_host(labels, opts):
    """Selects a host that can build with a given set of labels."""
    if labels.issubset(_HOST_LABELS[DOCKER_DEFAULT]):
        return DOCKER_DEFAULT
    possible_hosts = []
    for host, host_labels in _HOST_LABELS.iteritems():
        if labels.issubset(host_labels):
            possible_hosts.append(host)
    if not possible_hosts:
        raise ConfigurationError('no build slave supports this combination: ' + ' '.join(opts))
    # TODO: If there are multiple possible hosts, it would be better to
    # optimize the selection globally over all the configurations to
    # avoid assigning all the builds to the same host.
    for group in _SPECIAL_HOST_GROUPS:
        if set(possible_hosts).issubset(group):
            return possible_hosts[0]
        possible_hosts = [x for x in possible_hosts if x not in group]
    return possible_hosts[0]
