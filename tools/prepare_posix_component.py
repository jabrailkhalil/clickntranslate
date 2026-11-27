"""Prepare isolated Linux/macOS candidates natively; never build/publish the app."""
import argparse
from email.parser import BytesParser
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tarfile
import zipfile

PROJECT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(PROJECT/'src'),str(PROJECT/'tools')]
from component_catalog import current_platform
from component_download import ComponentDownloader
from component_store import file_digest


def unpack(path,target):
    target.mkdir(parents=True,exist_ok=True)
    with tarfile.open(path,'r:gz') as archive:
        members=archive.getmembers()
        if len(members)>100000 or sum(m.size for m in members)>4*1024**3:
            raise RuntimeError('Source archive expansion limit')
        archive.extractall(target,filter='data')


def fetch(item,target):
    target.parent.mkdir(parents=True,exist_ok=True)
    ComponentDownloader().artifact(item['url'],target,item)
    if target.stat().st_size!=item['size'] or file_digest(target)!=item['sha256']:
        raise RuntimeError('Source digest mismatch: '+target.name)


def audit(root):
    """Reject machine-specific absolute dependencies and unresolved libraries."""
    libraries={p.name for p in root.rglob('*') if p.is_file()}
    rows=[]
    base={'libc.so.6','libm.so.6','libdl.so.2','libpthread.so.0','librt.so.1','libutil.so.1',
          'libresolv.so.2','libgcc_s.so.1','libstdc++.so.6','ld-linux-x86-64.so.2'}
    for path in root.rglob('*'):
        if not path.is_file():continue
        with path.open('rb') as f:magic=f.read(4)
        relative=path.relative_to(root).as_posix()
        if sys.platform=='darwin' and magic in (b'\xcf\xfa\xed\xfe',b'\xfe\xed\xfa\xcf',b'\xca\xfe\xba\xbe',b'\xca\xfe\xba\xbf'):
            result=subprocess.run(['otool','-L',str(path)],capture_output=True,text=True,check=True)
            dependencies=[line.strip().split(' (',1)[0] for line in result.stdout.splitlines() if line.startswith('\t')]
            identity=subprocess.run(['otool','-D',str(path)],capture_output=True,text=True)
            own_ids={line.strip() for line in identity.stdout.splitlines()[1:]}
            dependencies=[dep for dep in dependencies if dep not in own_ids]
            for dep in dependencies:
                if dep.startswith('/') and not dep.startswith(('/usr/lib/','/System/Library/')):
                    raise RuntimeError('External Mach-O dependency: '+relative+' -> '+dep)
            rows.append({'path':relative,'dependencies':dependencies})
        elif sys.platform=='linux' and magic==b'\x7fELF':
            result=subprocess.run(['ldd',str(path)],capture_output=True,text=True)
            dependencies=[]
            for line in result.stdout.splitlines():
                if '=>' not in line:continue
                name,dest=line.strip().split('=>',1);name=name.strip();dest=dest.strip().split(' (',1)[0]
                if name not in base and name not in libraries:
                    raise RuntimeError('External ELF dependency: '+relative+' -> '+name+' '+dest)
                dependencies.append({'name':name,'resolution':'bundled' if name in libraries else 'base ABI'})
            rows.append({'path':relative,'dependencies':dependencies})
    return {'platform':current_platform(),'native_files':rows,'redistribution_review':False}


def native(output,runtime,recipe):
    source_root=output/'sources';prefix=output/'prefix'
    sources={}
    for item in recipe['sources']:
        path=output/(item['name']+'.tar.gz');fetch(item,path)
        target=source_root/item['name'];unpack(path,target)
        sources[item['name']]=next(p for p in target.iterdir() if p.is_dir())
    environment=os.environ.copy()
    environment['PKG_CONFIG_PATH']=str(prefix/'lib/pkgconfig')
    flags=['-DCMAKE_BUILD_TYPE=Release','-DCMAKE_POSITION_INDEPENDENT_CODE=ON','-DCMAKE_POLICY_VERSION_MINIMUM=3.5',
           '-DZLIB_USE_STATIC_LIBS=ON',
           '-DBUILD_SHARED_LIBS=OFF','-DCMAKE_INSTALL_PREFIX='+str(prefix),'-DCMAKE_PREFIX_PATH='+str(prefix)]
    if sys.platform=='darwin':
        flags+=['-DCMAKE_OSX_DEPLOYMENT_TARGET='+recipe['min_os'],'-DCMAKE_OSX_ARCHITECTURES='+platform.machine()]
    else:
        flags+=['-DCMAKE_EXE_LINKER_FLAGS=-static-libstdc++ -static-libgcc']
    def build(name,extra,*,target='install'):
        folder=output/('build-'+name)
        subprocess.run(['cmake','-S',str(sources[name]),'-B',str(folder),*flags,*extra],check=True,env=environment)
        subprocess.run(['cmake','--build',str(folder),'--parallel','4','--target',target],check=True,env=environment)
        return folder
    if recipe['engine']=='tesseract':
        if sys.platform=='darwin':
            flags+=['-DPNG_FRAMEWORK=OFF','-DPNG_STATIC=ON','-DCMAKE_FIND_FRAMEWORK=NEVER',
                    '-DZLIB_LIBRARY='+str(prefix/'lib/libz.a'),'-DPNG_LIBRARY='+str(prefix/'lib/libpng16.a')]
        build('zlib',['-DZLIB_BUILD_EXAMPLES=OFF'])
        build('libpng',['-DPNG_SHARED=OFF','-DPNG_TESTS=OFF','-DPNG_TOOLS=OFF'])
        build('leptonica',['-DBUILD_PROG=OFF','-DENABLE_GIF=OFF','-DENABLE_JPEG=OFF','-DENABLE_TIFF=OFF',
                          '-DENABLE_WEBP=OFF','-DENABLE_OPENJPEG=OFF','-DSW_BUILD=OFF'])
        folder=build('tesseract',['-DBUILD_TRAINING_TOOLS=OFF','-DBUILD_TESTS=OFF','-DDISABLE_CURL=ON',
                                  '-DDISABLE_ARCHIVE=ON','-DDISABLE_TIFF=ON','-DENABLE_NATIVE=OFF',
                                  '-DGRAPHICS_DISABLED=ON','-DOPENMP_BUILD=OFF'])
        executable=prefix/'bin/tesseract'
    else:
        # Archives lack .git metadata: use the authenticated tag's release number.
        info=sources['llama']/'cmake/build-info.cmake'
        text=info.read_text()
        if 'set(BUILD_NUMBER 0)' not in text:raise RuntimeError('Review upstream build-info layout')
        info.write_text(text.replace('set(BUILD_NUMBER 0)','set(BUILD_NUMBER '+recipe['version'].removeprefix('b')+')'))
        folder=build('llama',['-DGGML_NATIVE=OFF','-DGGML_METAL=OFF','-DGGML_OPENMP=OFF','-DGGML_CUDA=OFF',
            '-DGGML_AVX=OFF','-DGGML_AVX2=OFF','-DGGML_AVX512=OFF','-DGGML_FMA=OFF','-DGGML_F16C=OFF',
            '-DLLAMA_CURL=OFF','-DLLAMA_OPENSSL=OFF','-DLLAMA_BUILD_TESTS=OFF','-DLLAMA_BUILD_SERVER=ON',
            '-DLLAMA_BUILD_UI=OFF','-DLLAMA_BUILD_APP=OFF'],target='llama-cli')
        executable=folder/'bin/llama-cli'
    (runtime/'bin').mkdir(parents=True)
    shutil.copy2(executable,runtime/'bin'/executable.name)
    if recipe['engine']=='tesseract':
        for name in ('configs','tessconfigs'):
            shutil.copytree(sources['tesseract']/'tessdata'/name,runtime/'tessdata'/name)
    for name,source in sources.items():
        for path in source.rglob('*'):
            if path.is_file() and (path.name.upper().startswith(('LICENSE','COPYING','NOTICE','COPYRIGHT'))):
                target=runtime/'licenses'/name/path.relative_to(source)
                target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
    (runtime/'SOURCE-PROVENANCE.json').write_text(json.dumps(recipe,indent=2)+'\n')


def python_runtime(output,runtime,recipe):
    source=output/'python.tar.gz';fetch(recipe['python_source'],source)
    unpack(source,runtime)
    # These non-interactive workers do not use a terminal database. Its Unix
    # case aliases (Eterm/eterm, etc.) cannot go in a portable safe ZIP.
    terminfo=runtime/'python/share/terminfo'
    if terminfo.is_symlink():terminfo.unlink()
    elif terminfo.exists():
        if not terminfo.resolve().is_relative_to(runtime.resolve()):raise RuntimeError('Invalid terminal data path')
        shutil.rmtree(terminfo)
    if recipe.get('zlib_source'):
        archive=output/'zlib-source.tar.gz';fetch(recipe['zlib_source'],archive)
        sources=output/'zlib-source';unpack(archive,sources)
        source=next(p for p in sources.iterdir() if p.is_dir());build=output/'zlib-build'
        subprocess.run(['cmake','-S',str(source),'-B',str(build),'-DCMAKE_BUILD_TYPE=Release',
                        '-DZLIB_BUILD_EXAMPLES=OFF','-DCMAKE_POSITION_INDEPENDENT_CODE=ON'],check=True)
        subprocess.run(['cmake','--build',str(build),'--parallel','4','--target','zlib'],check=True)
        library=next(p for p in build.glob('libz.so.*') if p.is_file() and not p.is_symlink())
        shutil.copy2(library,runtime/'python/lib/libz.so.1')
        licenses=runtime/'licenses/zlib';licenses.mkdir(parents=True)
        for path in source.glob('*'):
            if path.name.upper().startswith(('LICENSE','COPYING','README')) and path.is_file():shutil.copy2(path,licenses/path.name)
    # Optional GUI/password modules are not used by these workers and would
    # introduce distro Tk/X11/libcrypt dependencies into an otherwise private SDK.
    extensions=runtime/'python/lib/python3.12/lib-dynload'
    for pattern in ('_tkinter*','_crypt*'):
        for path in extensions.glob(pattern):
            if path.is_file():path.unlink()
    interpreter=runtime/'python/bin/python3.12'
    wheels=output/'wheelhouse';wheels.mkdir()
    for wheel in recipe.get('source_wheels',[]):fetch(wheel,wheels/wheel['filename'])
    subprocess.run([str(interpreter),'-I','-m','pip','download','--only-binary=:all:',
        '--find-links',str(wheels),'--dest',str(wheels),*recipe['requirements']],check=True)
    if recipe.get('requirements_no_deps'):
        subprocess.run([str(interpreter),'-I','-m','pip','download','--only-binary=:all:','--no-deps',
            '--dest',str(wheels),*recipe['requirements_no_deps']],check=True)
    locks=[]
    for wheel in sorted(wheels.glob('*.whl')):
        with zipfile.ZipFile(wheel) as archive:
            meta=BytesParser().parsebytes(archive.read(next(n for n in archive.namelist() if n.endswith('.dist-info/METADATA'))))
        locks.append(f"{meta['Name']}=={meta['Version']} --hash=sha256:{file_digest(wheel)}")
    lock=output/'requirements.lock';lock.write_text('\n'.join(locks)+'\n')
    subprocess.run([str(interpreter),'-I','-m','pip','install','--no-index','--no-deps','--require-hashes',
        '--find-links',str(wheels),'-r',str(lock)],check=True)
    site=runtime/'python/lib/python3.12/site-packages'
    for name in recipe['adapter_files']:shutil.copy2(PROJECT/'src'/name,site/name)
    shutil.copy2(lock,runtime/'requirements.lock')


def prepare(output,recipe_path):
    recipe=json.loads(recipe_path.read_bytes());target=current_platform()
    if any(target[key]!=recipe[key] for key in ('os','arch')):raise RuntimeError('Prepare on the exact native platform/architecture')
    if output.exists():raise RuntimeError('Use a fresh preparation directory')
    output.mkdir(parents=True);runtime=output/'runtime';runtime.mkdir()
    if recipe['engine'] in ('tesseract','hymt'):native(output,runtime,recipe)
    else:python_runtime(output,runtime,recipe)
    (runtime/'COMPONENT.json').write_text(json.dumps(recipe,indent=2)+'\n')
    shutil.copy2(PROJECT/'LICENSE',runtime/'LICENSE-ClicknTranslate.txt')
    (runtime/'NATIVE-DEPENDENCIES.json').write_text(json.dumps(audit(runtime),indent=2)+'\n')
    # Relocation is tested before archiving; no build/interpreter paths may be required.
    moved=output/'relocated runtime with spaces';runtime.rename(moved)
    executable=moved/('bin/'+('tesseract' if recipe['engine']=='tesseract' else 'llama-cli') if recipe['engine'] in ('tesseract','hymt') else 'python/bin/python3.12')
    subprocess.run([str(executable),'--version'],check=True,cwd=moved)
    moved.rename(runtime)
    archive=output/recipe['filename'];expanded=0;names=set()
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as bundle:
        for path in sorted(runtime.rglob('*')):
            if not path.is_file() or '__pycache__' in path.parts or path.suffix=='.pyc':continue
            real=path.resolve()
            if not real.is_relative_to(runtime.resolve()):raise RuntimeError('Link escapes prepared runtime')
            relative=path.relative_to(runtime).as_posix()
            if relative.casefold() in names:raise RuntimeError('Case collision in prepared runtime: '+relative)
            names.add(relative.casefold())
            expanded+=real.stat().st_size
            # Flatten internal symlinks; the client never installs archive links.
            info=zipfile.ZipInfo.from_file(real,arcname=path.relative_to(runtime).as_posix())
            info.compress_type=zipfile.ZIP_DEFLATED
            with real.open('rb') as source,bundle.open(info,'w') as dest:shutil.copyfileobj(source,dest)
    description={'filename':archive.name,'sha256':file_digest(archive),'size':archive.stat().st_size,
                 'unpacked_size':expanded,'recipe':recipe}
    (output/'runtime-artifact.json').write_text(json.dumps(description,indent=2)+'\n')
    print(json.dumps({k:v for k,v in description.items() if k!='recipe'}),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--recipe',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();prepare(args.output.resolve(),args.recipe)
