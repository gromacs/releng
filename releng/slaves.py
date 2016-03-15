"""
Information about Jenkins build slaves
"""
from common import ConfigurationError

BS_CENTOS63 = 'bs_centos63'
BS_MAC = 'bs_mac'
BS_MIC = 'bs_mic'
BS_NIX1004 = 'bs_nix1004'
BS_NIX1204 = 'bs_nix1204'
BS_NIX1310 = 'bs_nix1310'
BS_NIX1404 = 'bs_nix1404'
BS_NIX64 = 'bs_nix64'
BS_NIX_AMD_GPU = 'bs_nix-amd_gpu'
BS_NIX_AMD = 'bs_nix-amd'
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
_HOST_LABELS = {
            BS_CENTOS63:    { 'gcc-4.4', 'gcc-5.2',
                              'clang-3.4',
                              'cuda-5.5',
                              'cmake-2.8.12.2',
                              'sse2', 'sse4.1', 'avx_128_fma',
                              'mpi',
                              'valgrind' },
            BS_MIC:         { 'gcc-4.4', 'gcc-4.7', 'gcc-4.8', 'gcc-4.9', 'gcc-5.2',
                              'clang-3.4',
                              'icc-14.0', 'icc-16.0',
                              'phi',
                              'cmake-2.8.12.2', 'cmake-3.3.2',
                              'sse2', 'sse4.1', 'avx_256', 'mic' },
            BS_NIX1004:     { 'gcc-4.1', 'gcc-4.3', 'gcc-4.4',
                              'cmake-2.8.8',
                              'sse2' },
            BS_NIX64:       { 'gcc-4.4', 'gcc-4.5', 'gcc-4.6', 'gcc-4.7',
                              'clang-3.4',
                              'icc-12.1',
                              'cmake-2.8.9',
                              'sse2',
                              'mpi' },
            BS_MAC:         { 'gcc-4.2', 'gcc-4.4', 'gcc-4.5', 'gcc-4.6', 'gcc-4.7', 'gcc-4.8', 'gcc-4.9',
                              'clang-3.4',
                              'icc-12.1', 'icc-13.0', 'icc-15.0', 'icc-16.0',
                              'cmake-3.2.1',
                              'sse2', 'sse4.1',
                              'x11' },
            BS_NIX1204:     { 'gcc-4.4', 'gcc-4.5', 'gcc-4.6', 'gcc-4.7', 'gcc-4.8',
                              'clang-3.3', 'clang-3.6',
                              'cuda-5.0', 'cuda-5.5', 'cuda-6.0', 'cuda-6.5', 'cuda-7.0',
                              'cmake-2.8.8',
                              'sse2', 'sse4.1', 'avx_256', 'avx2_256',
                              'mpi', 'x11',
                              'valgrind' },
            BS_NIX1310:     { 'gcc-4.4', 'gcc-4.6', 'gcc-4.7', 'gcc-4.8', 'gcc-4.9',
                              'clang-3.4',
                              'icc-15.0', 'icc-16.0',
                              'cuda-5.0', 'cuda-5.5', 'cuda-6.0', 'cuda-6.5', 'cuda-7.0', 'cuda-7.5',
                              'cmake-2.8.11.2',
                              'sse2', 'sse4.1', 'avx_256', 'avx2_256',
                              'mpi', 'x11',
                              'valgrind', 'tsan' },
            BS_NIX1404:     { 'gcc-4.4', 'gcc-4.6', 'gcc-4.7', 'gcc-4.8', 'gcc-4.9', 'gcc-5.1',
                              'clang-3.5', 'clang-3.6',
                              'cuda-6.0', 'cuda-6.5', 'cuda-7.0',
                              'cmake-2.8.12.2', 'cmake-3.0.2',
                              'sse2', 'sse4.1', 'avx_128_fma',
                              'mpi',
                              'valgrind', 'msan' },
            BS_NIX_AMD_GPU: { 'gcc-4.8',
                              'clang-3.5', 'clang-3.6',
                              'amdappsdk-3.0',
                              'cmake-2.8.12.2',
                              'sse2', 'sse4.1', 'avx_128_fma',
                              'mpi' },
            BS_NIX_AMD:     { 'gcc-4.8', 'gcc-5.2',
                              'clang-3.5', 'clang-3.6', 'clang-3.7',
                              'cmake-2.8.12.2',
                              'sse2', 'sse4.1', 'avx_128_fma',
                              'mpi' },
            BS_WIN2008:     { 'msvc-2010',
                              'icc-12.1' },
            BS_WIN2012R2:   { 'msvc-2013', 'msvc-2015',
                              'icc-16.0' },
            DOCKER_DEFAULT: {} # TODO
        }

_WINDOWS_HOSTS = {BS_WIN2008, BS_WIN2012R2}

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
    # Use Windows machines only for builds that can only be run there.
    if set(possible_hosts).issubset(_WINDOWS_HOSTS):
        return possible_hosts[0]
    possible_hosts = [x for x in possible_hosts if x not in _WINDOWS_HOSTS]
    return possible_hosts[0]
