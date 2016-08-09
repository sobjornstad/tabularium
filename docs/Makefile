manual.html: manual.md resources/top.html resources/bottom.html Makefile
	python addAnchors.py manual.md tmp.md && markdown tmp.md > tmp.html && cat resources/top.html tmp.html resources/bottom.html > manual.html && rm tmp.html && rm tmp.md
