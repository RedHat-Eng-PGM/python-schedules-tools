NAME = schedules-tools


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


rpm: prebuild
	rpmbuild --define "dist .el7eso" -ba build/$(NAME).spec


rpm-copr: rpm
	devel-tools/copr.py ~/rpmbuild/SRPMS/$(NAME)-$(version)-$(release).$(checkout).el7eso.src.rpm

rpm-brew: rpm
	brew build eso-rhel-7-candidate ~/rpmbuild/SRPMS/$(NAME)-$(version)-$(release).$(checkout).el7eso.src.rpm 

copr: prebuild
	devel-tools/copr.py ~/rpmbuild/SRPMS/$(NAME)-$(version)-$(release).$(checkout).el7eso.src.rpm

brew: prebuild
	brew build eso-rhel-7-candidate ~/rpmbuild/SRPMS/$(NAME)-$(version)-$(release).$(checkout).el7eso.src.rpm 


prebuild: source
	$(eval version := $(shell cat build/version.txt))
	echo "%define version $(version)" > build/$(NAME).spec
	$(eval release := $(shell cat build/release.txt))
	echo "%define release $(release)" >> build/$(NAME).spec
	$(eval checkout := $(shell cat build/checkout.txt))
	echo "%define checkout $(checkout)" >> build/$(NAME).spec
	cat spec/$(NAME).spec.in >> build/$(NAME).spec
	@python scripts/rpm_log.py >> build/$(NAME).spec
	mkdir -p ~/rpmbuild/SOURCES
	cp dist/$(NAME)-$(version).tar.gz ~/rpmbuild/SOURCES


clean:
	@python setup.py clean
	rm -f MANIFEST build/$(NAME).spec
	find . -\( -name "*.pyc" -o -name '*.pyo' -o -name "*~" -\) -delete

install:
	@python setup.py install


log:
	@python scripts/rpm_log.py

source: clean
	mkdir -p build
	@python setup.py sdist

