debian:
	cp nginx-nr-agent.py debian/
	mkdir -p ~/nginx-nr-agent-2.0.0/
	cp -r debian ~/nginx-nr-agent-2.0.0/
	cd ~/nginx-nr-agent-2.0.0/
	dpkg-buildpackage
	mkdir -p build_output/
	mv /nginx-nr-agent* build_output/

rpm:
	cp nginx-nr-agent.py rpm/SOURCES/
	mkdir -p ~/rpmbuild
	cp -r rpm/* ~/rpmbuild/
	rpmbuild -bb ~/rpmbuild/SPECS/nginx-nr-agent.spec
	mv ~/rpmbuild/RPMS/noarch/nginx-nr-agent* build_output/

.PHONY: debian rpm

