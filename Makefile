all: help


help:
	@echo "Usage: make <target>"
	@echo
	@echo "Available targets are:"
	@echo " help                    show this text"
	@echo " clean                   remove python bytecode and temp files"
	@echo " install                 install program on current system"
	@echo " log                     prepare changelog for spec file"
	@echo " source                  create source tarball"


rpm: source
	mkdir -p ~/rpmbuild/SOURCES
	cp dist/*.tar.gz ~/rpmbuild/SOURCES

	rpmbuild --define "dist .el7eso" -ba dist/*.spec


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
