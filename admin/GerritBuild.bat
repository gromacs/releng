mkdir gromacs
cd gromacs
git init && git fetch git://git.gromacs.org/gromacs.git refs/heads/release-4-5-patches && git checkout -q -f FETCH_HEAD && git clean -fd && python -u ../GerritBuild.py
