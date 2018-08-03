debian:
	cp nginx-nr-agent.py debian/
	dpkg-buildpackage
	mkdir -p build_output/
	mv ../nginx-nr-agent*.deb build_output/
	mv ../nginx-nr-agent*.tar.gz build_output/
	rm -f ../nginx-nr-agent*

rpm:
	cp nginx-nr-agent.py rpm/SOURCES/
	mkdir -p ~/rpmbuild/
	cp -r rpm/* ~/rpmbuild/
	rpmbuild -bb ~/rpmbuild/SPECS/nginx-nr-agent.spec
	mkdir -p build_output/
	mv ~/rpmbuild/RPMS/noarch/nginx-nr-agent*.rpm build_output/

clean:
	rm -rf build_output/
	rm -rf ~/rpmbuild/

.PHONY: debian rpm

