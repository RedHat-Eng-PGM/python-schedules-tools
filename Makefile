all: help

# optionally specify directory of created SRPM
SRPM_OUTDIR ?= ""

ifneq (${SRPM_OUTDIR}, "")
	SRPM_OUTDIR_PARAM := --define "_srcrpmdir $(SRPM_OUTDIR)"
endif


help:
	@echo "Usage: make <target>"
	@echo
	@echo "Available targets are:"
	@echo " help                    show this text"
	@echo " clean                   remove python bytecode and temp files"
	@echo " install                 install program on current system"
	@echo " log                     prepare changelog for spec file"
	@echo " source                  create source tarball"
	@echo " rpm                     create rpm"
	@echo " srpm                    create srpm"
	@echo ""
	@echo "Optinal param:"
	@echo " SRPM_OUTDIR             to specify non-default directory to place SRPM"


srpm: prepare_source
	rpmbuild --define "dist .el7eso" ${SRPM_OUTDIR_PARAM} -bs dist/*.spec


rpm: prepare_source
	rpmbuild --define "dist .el7eso" -bb dist/*.spec


pypi: source
	twine upload dist/*tar.gz -r pypi-pgm

pypitest: source
	twine upload dist/*tar.gz -r pypitest-pgm 


clean:
	@python setup.py clean
	find . -\( -name "*.pyc" -o -name '*.pyo' -o -name "*~" -\) -delete
	rm -rf ./*.egg-info ./dist

install:
	@python setup.py install


log:
	@python scripts/rpm_log.py

source: clean
	@python setup.py sdist

prepare_source: source
	mkdir -p ~/rpmbuild/SOURCES
	cp dist/*.tar.gz ~/rpmbuild/SOURCES

