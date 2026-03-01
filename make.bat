@echo off
setlocal EnableExtensions

if not defined PYTHON set "PYTHON=python"
if not defined SPHINXBUILD set "SPHINXBUILD=sphinx-build"
if not defined SPHINXOPTS set "SPHINXOPTS="
if not defined BUILDDIR set "BUILDDIR=build"
if not defined PAPER set "PAPER="
if not defined VERSION set "VERSION=%MAYA_VERSION%"
if not defined PUBLISH_ROOT set "PUBLISH_ROOT=."
if not defined BUILD_SOURCE set "BUILD_SOURCE=%BUILDDIR%\source\%VERSION%"
if not defined DOCTREES set "DOCTREES=%BUILDDIR%\doctrees\%VERSION%"

if /I "%PAPER%"=="a4" (
    set "PAPEROPT=-D latex_paper_size=a4"
) else if /I "%PAPER%"=="letter" (
    set "PAPEROPT=-D latex_paper_size=letter"
) else (
    set "PAPEROPT="
)

set "ALLSPHINXOPTS=-d %DOCTREES% %PAPEROPT% %SPHINXOPTS% %BUILD_SOURCE%"
set "I18NSPHINXOPTS=%PAPEROPT% %SPHINXOPTS% %BUILD_SOURCE%"

if "%~1"=="" goto help
set "TARGET=%~1"

where %SPHINXBUILD% >nul 2>nul
if errorlevel 1 (
  echo The '%SPHINXBUILD%' command was not found. Make sure you have Sphinx installed, then set SPHINXBUILD to the full path of the executable.
  exit /b 1
)

if /I "%TARGET%"=="help" goto help
if /I "%TARGET%"=="clean" goto clean
if /I "%TARGET%"=="html" goto html
if /I "%TARGET%"=="dirhtml" goto dirhtml
if /I "%TARGET%"=="singlehtml" goto singlehtml
if /I "%TARGET%"=="pickle" goto pickle
if /I "%TARGET%"=="json" goto json
if /I "%TARGET%"=="htmlhelp" goto htmlhelp
if /I "%TARGET%"=="qthelp" goto qthelp
if /I "%TARGET%"=="applehelp" goto applehelp
if /I "%TARGET%"=="devhelp" goto devhelp
if /I "%TARGET%"=="epub" goto epub
if /I "%TARGET%"=="latex" goto latex
if /I "%TARGET%"=="latexpdf" goto latexpdf
if /I "%TARGET%"=="latexpdfja" goto latexpdfja
if /I "%TARGET%"=="text" goto text
if /I "%TARGET%"=="man" goto man
if /I "%TARGET%"=="texinfo" goto texinfo
if /I "%TARGET%"=="info" goto info
if /I "%TARGET%"=="gettext" goto gettext
if /I "%TARGET%"=="changes" goto changes
if /I "%TARGET%"=="linkcheck" goto linkcheck
if /I "%TARGET%"=="doctest" goto doctest
if /I "%TARGET%"=="coverage" goto coverage
if /I "%TARGET%"=="xml" goto xml
if /I "%TARGET%"=="pseudoxml" goto pseudoxml
if /I "%TARGET%"=="publish-version" goto publish-version
if /I "%TARGET%"=="publish-only" goto publish-only
if /I "%TARGET%"=="prepare-source" goto prepare-source

echo Unknown target: %TARGET%
goto help

:require-version
if defined VERSION set "BUILD_VERSION=%VERSION%"
if not defined BUILD_VERSION if defined MAYA_VERSION set "BUILD_VERSION=%MAYA_VERSION%"
if defined BUILD_VERSION if not "%BUILD_VERSION%"=="" goto version_ok

echo Version is required. Example: set VERSION=2026 before run.
echo Or set MAYA_VERSION environment variable.
exit /b 1

:version_ok
if not defined SITE_DIR set "SITE_DIR=%BUILDDIR%\html\%BUILD_VERSION%"
if not defined BUILD_SOURCE set "BUILD_SOURCE=%BUILDDIR%\source\%BUILD_VERSION%"
if not defined DOCTREES set "DOCTREES=%BUILDDIR%\doctrees\%BUILD_VERSION%"
set "ALLSPHINXOPTS=-d %DOCTREES% %PAPEROPT% %SPHINXOPTS% %BUILD_SOURCE%"
set "I18NSPHINXOPTS=%PAPEROPT% %SPHINXOPTS% %BUILD_SOURCE%"
goto :eof

:help
echo Please use `make.bat <target>` where <target> is one of
echo   html       to make standalone HTML files (from data/nodes/VERSION)
echo   dirhtml    to make HTML files named index.html in directories
echo   singlehtml to make a single large HTML file
echo   pickle     to make pickle files
echo   json       to make JSON files
echo   htmlhelp   to make HTML files and a HTML help project
echo   qthelp     to make HTML files and a qthelp project
echo   applehelp  to make an Apple Help Book
echo   devhelp    to make HTML files and a Devhelp project
echo   epub       to make an epub
echo   latex      to make LaTeX files, you can set PAPER=a4 or PAPER=letter
echo   latexpdf   to make LaTeX files and run them through pdflatex
echo   latexpdfja to make LaTeX files and run them through platex/dvipdfmx
echo   text       to make text files
echo   man        to make manual pages
echo   texinfo    to make Texinfo files
echo   info       to make Texinfo files and run these through makeinfo
echo   gettext    to make PO message catalogs
echo   changes    to make an overview of all changed/added/deprecated items
echo   xml        to make Docutils-native XML files
echo   pseudoxml  to make pseudoxml-XML files for display purposes
echo   linkcheck  to check all external links for integrity
echo   doctest    to run all doctests embedded in the documentation (if enabled)
echo   coverage   to run coverage check of the documentation (if enabled)
echo   prepare-source [VERSION=2026] to prepare %BUILD_SOURCE% from data/nodes
echo   publish-version VERSION=2026 to build+publish from %BUILDDIR%\html\VERSION to ./%BUILD_VERSION% and ./latest
echo   publish-only VERSION=2026 to publish current build/html/VERSION only
goto end

:clean
rmdir /s /q "%BUILDDIR%" >nul 2>nul
mkdir "%BUILDDIR%" >nul 2>nul
goto end

:html
call :require-version
if errorlevel 1 exit /b 1
call :prepare-source
if errorlevel 1 exit /b 1
if exist "%SITE_DIR%" rmdir /s /q "%SITE_DIR%"
%SPHINXBUILD% -b html -d "%DOCTREES%" %PAPEROPT% %SPHINXOPTS% "%BUILD_SOURCE%" "%SITE_DIR%"
if errorlevel 1 exit /b 1
echo.
echo Build finished. The HTML pages are in %SITE_DIR%.
goto end

:dirhtml
%SPHINXBUILD% -b dirhtml %ALLSPHINXOPTS% %BUILDDIR%\dirhtml
if errorlevel 1 exit /b 1
echo.
echo Build finished. The HTML pages are in %BUILDDIR%\dirhtml.
goto end

:singlehtml
%SPHINXBUILD% -b singlehtml %ALLSPHINXOPTS% %BUILDDIR%\singlehtml
if errorlevel 1 exit /b 1
echo.
echo Build finished. The HTML page is in %BUILDDIR%\singlehtml.
goto end

:pickle
%SPHINXBUILD% -b pickle %ALLSPHINXOPTS% %BUILDDIR%\pickle
if errorlevel 1 exit /b 1
echo.
echo Build finished; now you can process the pickle files.
goto end

:json
%SPHINXBUILD% -b json %ALLSPHINXOPTS% %BUILDDIR%\json
if errorlevel 1 exit /b 1
echo.
echo Build finished; now you can process the JSON files.
goto end

:htmlhelp
%SPHINXBUILD% -b htmlhelp %ALLSPHINXOPTS% %BUILDDIR%\htmlhelp
if errorlevel 1 exit /b 1
echo.
echo Build finished; now you can run HTML Help Workshop with the .hhp project file in %BUILDDIR%\htmlhelp.
goto end

:qthelp
%SPHINXBUILD% -b qthelp %ALLSPHINXOPTS% %BUILDDIR%\qthelp
if errorlevel 1 exit /b 1
echo.
echo Build finished; now you can run "qcollectiongenerator" with the .qhcp project file in %BUILDDIR%\qthelp, like this:
echo   qcollectiongenerator %BUILDDIR%\qthelp\maya-nodes.qhcp
echo To view the help file:
echo   assistant -collectionFile %BUILDDIR%\qthelp\maya-nodes.qhc
goto end

:applehelp
%SPHINXBUILD% -b applehelp %ALLSPHINXOPTS% %BUILDDIR%\applehelp
if errorlevel 1 exit /b 1
echo.
echo Build finished. The help book is in %BUILDDIR%\applehelp.
goto end

:devhelp
%SPHINXBUILD% -b devhelp %ALLSPHINXOPTS% %BUILDDIR%\devhelp
if errorlevel 1 exit /b 1
echo.
echo Build finished.
echo To view the help file:
echo   mkdir -p %USERPROFILE%\.local\share\devhelp\maya-nodes
echo   ln -s %BUILDDIR%\devhelp %USERPROFILE%\.local\share\devhelp\maya-nodes
echo   devhelp
goto end

:epub
%SPHINXBUILD% -b epub %ALLSPHINXOPTS% %BUILDDIR%\epub
if errorlevel 1 exit /b 1
echo.
echo Build finished. The epub file is in %BUILDDIR%\epub.
goto end

:latex
%SPHINXBUILD% -b latex %ALLSPHINXOPTS% %BUILDDIR%\latex
if errorlevel 1 exit /b 1
echo.
echo Build finished; the LaTeX files are in %BUILDDIR%\latex.
echo Run "make" in that directory to run these through (pdf)latex (use "make latexpdf" here to do that automatically).
goto end

:latexpdf
%SPHINXBUILD% -b latex %ALLSPHINXOPTS% %BUILDDIR%\latex
if errorlevel 1 exit /b 1
echo Running LaTeX files through pdflatex...
cd /d "%BUILDDIR%\latex"
if exist Makefile.nmake (
  nmake all-pdf
) else (
  make -C . all-pdf
)
if errorlevel 1 exit /b 1
cd /d "%~dp0"
echo pdflatex finished; the PDF files are in %BUILDDIR%\latex.
goto end

:latexpdfja
%SPHINXBUILD% -b latex %ALLSPHINXOPTS% %BUILDDIR%\latex
if errorlevel 1 exit /b 1
echo Running LaTeX files through platex and dvipdfmx...
cd /d "%BUILDDIR%\latex"
if exist Makefile.nmake (
  nmake all-pdf-ja
) else (
  make -C . all-pdf-ja
)
if errorlevel 1 exit /b 1
cd /d "%~dp0"
echo pdflatex finished; the PDF files are in %BUILDDIR%\latex.
goto end

:text
%SPHINXBUILD% -b text %ALLSPHINXOPTS% %BUILDDIR%\text
if errorlevel 1 exit /b 1
echo.
echo Build finished. The text files are in %BUILDDIR%\text.
goto end

:man
%SPHINXBUILD% -b man %ALLSPHINXOPTS% %BUILDDIR%\man
if errorlevel 1 exit /b 1
echo.
echo Build finished. The manual pages are in %BUILDDIR%\man.
goto end

:texinfo
%SPHINXBUILD% -b texinfo %ALLSPHINXOPTS% %BUILDDIR%\texinfo
if errorlevel 1 exit /b 1
echo.
echo Build finished. The Texinfo files are in %BUILDDIR%\texinfo.
echo Run "make" in that directory to run these through makeinfo (use "make info" here to do that automatically).
goto end

:info
%SPHINXBUILD% -b texinfo %ALLSPHINXOPTS% %BUILDDIR%\texinfo
if errorlevel 1 exit /b 1
echo Running Texinfo files through makeinfo...
cd /d "%BUILDDIR%\texinfo"
make info
if errorlevel 1 exit /b 1
cd /d "%~dp0"
echo makeinfo finished; the Info files are in %BUILDDIR%\texinfo.
goto end

:gettext
%SPHINXBUILD% -b gettext %I18NSPHINXOPTS% %BUILDDIR%\locale
if errorlevel 1 exit /b 1
echo.
echo Build finished. The message catalogs are in %BUILDDIR%\locale.
goto end

:changes
%SPHINXBUILD% -b changes %ALLSPHINXOPTS% %BUILDDIR%\changes
if errorlevel 1 exit /b 1
echo.
echo The overview file is in %BUILDDIR%\changes.
goto end

:linkcheck
%SPHINXBUILD% -b linkcheck %ALLSPHINXOPTS% %BUILDDIR%\linkcheck
if errorlevel 1 exit /b 1
echo.
echo Link check complete; look for any errors in the above output or in %BUILDDIR%\linkcheck\output.txt.
goto end

:doctest
%SPHINXBUILD% -b doctest %ALLSPHINXOPTS% %BUILDDIR%\doctest
if errorlevel 1 exit /b 1
echo.
echo Testing of doctests in the sources finished, look at the results in %BUILDDIR%\doctest\output.txt.
goto end

:coverage
%SPHINXBUILD% -b coverage %ALLSPHINXOPTS% %BUILDDIR%\coverage
if errorlevel 1 exit /b 1
echo.
echo Testing of coverage in the documentation finished, look at the results in %BUILDDIR%\coverage\python.txt.
goto end

:xml
%SPHINXBUILD% -b xml %ALLSPHINXOPTS% %BUILDDIR%\xml
if errorlevel 1 exit /b 1
echo.
echo Build finished. The XML files are in %BUILDDIR%\xml.
goto end

:pseudoxml
%SPHINXBUILD% -b pseudoxml %ALLSPHINXOPTS% %BUILDDIR%\pseudoxml
if errorlevel 1 exit /b 1
echo.
echo Build finished. The pseudo-XML files are in %BUILDDIR%\pseudoxml.
goto end

:publish-version
call :require-version
if errorlevel 1 exit /b 1
call :html
if errorlevel 1 exit /b 1
call :publish-only
if errorlevel 1 exit /b 1
goto end

:publish-only
call :require-version
if errorlevel 1 exit /b 1
%PYTHON% tool/publish_version_site.py --version "%BUILD_VERSION%" --site-dir "%SITE_DIR%" --publish-root "%PUBLISH_ROOT%"
if errorlevel 1 exit /b 1
goto end

:prepare-source
call :require-version
if errorlevel 1 exit /b 1
%PYTHON% tool/prepare_build_source.py --version "%BUILD_VERSION%" --output-root "%BUILD_SOURCE%"
if errorlevel 1 exit /b 1
goto end

:end
exit /b 0
