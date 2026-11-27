"""Prepare a pinned native Hy-MT candidate; never build the application."""
import argparse
import json
from pathlib import Path
import shutil
import sys
import zipfile

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PROJECT/'src'))
from component_catalog import parse_catalog
from component_download import ComponentDownloader
from component_store import ComponentStore, file_digest


def fetch(description, path):
    if not path.exists():
        ComponentDownloader().artifact(description['url'],path,description)
    if path.stat().st_size != description['size'] or file_digest(path) != description['sha256']:
        raise RuntimeError('Pinned source checksum mismatch: '+path.name)
    return path


def native_files(source):
    import pefile
    from runtime_dlls import SYSTEM
    dlls={p.name.lower():p for p in source.glob('*.dll')}
    # ggml backends and the current CLI implementation are selected with
    # LoadLibrary rather than normal PE imports. Keep every CPU fallback.
    pending=[source/'llama-cli.exe',*source.glob('ggml*.dll')]
    if (source/'llama-cli-impl.dll').exists():pending.append(source/'llama-cli-impl.dll')
    selected={}
    while pending:
        path=pending.pop()
        if path.name.lower() in selected:continue
        selected[path.name.lower()]=path
        binary=pefile.PE(str(path),fast_load=True)
        try:
            binary.parse_data_directories(directories=[1,13])
            for entry in [*getattr(binary,'DIRECTORY_ENTRY_IMPORT',()),*getattr(binary,'DIRECTORY_ENTRY_DELAY_IMPORT',())]:
                name=entry.dll.decode('ascii').lower()
                if name in dlls:pending.append(dlls[name])
                elif (name.removesuffix('.dll') not in SYSTEM
                      and not name.startswith(('api-ms-win-','ext-ms-win-','msvcp140','vcruntime140','concrt140'))):
                    raise RuntimeError('Unknown llama.cpp dependency: '+name)
        finally:binary.close()
    return sorted(selected.values())


def prepare(output, recipe_path):
    from prepare_msvc import prepare as prepare_msvc
    from runtime_dlls import audit
    recipe=json.loads(recipe_path.read_bytes())
    if output.exists():raise RuntimeError('Use a fresh output directory')
    output.mkdir(parents=True)
    upstream=fetch(recipe['runner'],output/'upstream.zip')
    source=output/'upstream'
    ComponentStore.extract(upstream,source,recipe['runner']['unpacked_size'])
    runtime=output/'runtime';runtime.mkdir()
    selected=native_files(source)
    for path in selected:shutil.copy2(path,runtime/path.name)
    for path in source.rglob('*'):
        if path.is_file() and ('license' in path.name.lower() or 'notice' in path.name.lower()):
            target=runtime/'upstream-notices'/path.relative_to(source);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
    fetch(recipe['runner_license'],runtime/'LICENSE-llama.cpp.txt')
    prepare_msvc(output,runtime,recipe['msvc'])
    native=audit(runtime,'llama-cli.exe')
    (runtime/'NATIVE-DEPENDENCIES.json').write_text(json.dumps(native,indent=2),encoding='utf-8')
    (runtime/'COMPONENT.json').write_text(json.dumps(recipe,indent=2),encoding='utf-8')
    (runtime/'THIRD_PARTY_NOTICES.txt').write_text(
        'llama.cpp: MIT, LICENSE-llama.cpp.txt; upstream notices are retained.\n'
        'Microsoft runtime: exact sources/hashes in MICROSOFT-RUNTIME.json; https://aka.ms/vc14/license.\n'
        'Hy-MT model and its License.txt/README.md are separate authenticated files.\n',encoding='utf-8')
    filename=f"hymt-windows-x64-{recipe['runner']['tag']}-runtime.zip"
    archive=output/filename
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as target:
        for path in sorted(runtime.rglob('*')):
            if path.is_file():target.write(path,path.relative_to(runtime).as_posix())
    summary={'filename':filename,'size':archive.stat().st_size,'sha256':file_digest(archive),
        'unpacked_size':sum(p.stat().st_size for p in runtime.rglob('*') if p.is_file()),
        'recipe':recipe,'original_binary_files':[p.name for p in selected],
        'redistribution_review':False,'application_build':False}
    (output/'runtime-artifact.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    catalog=describe(summary)
    (output/'catalog-candidate.json').write_text(json.dumps(catalog,indent=2),encoding='utf-8')
    print(json.dumps({key:summary[key] for key in ('filename','size','sha256','unpacked_size')}))


def describe(runtime):
    recipe=runtime['recipe'];tag=recipe['runner']['tag'];release=f"hymt-windows-x64-{tag}-r{recipe['revision']}"
    artifacts={runtime['sha256']:{'size':runtime['size'],'unpacked_size':runtime['unpacked_size'],
        'urls':[f'https://github.com/jabrailkhalil/clickntranslate-components/releases/download/{release}/'+runtime['filename']]}}
    files=[{'kind':'zip','sha256':runtime['sha256'],'destination':'runtime'}]
    for item in [recipe['model'],*recipe['docs']]:
        artifacts[item['sha256']]={'size':item['size'],'urls':[item['url']]}
        files.append({'kind':'file','sha256':item['sha256'],'destination':'models/'+item['name']})
    return parse_catalog(json.dumps({'schema':1,'revision':5,'artifacts':artifacts,'bundles':[
        {'id':release,'component':'translation.hymt','revision':recipe['revision'],'contract':recipe['contract'],
         'channel':recipe['channel'],'os':'windows','arch':'x86_64','min_os':recipe['min_os'],'app':recipe['app'],
         'runtime':'native','executable':'runtime/llama-cli.exe','model':'models/'+recipe['model']['name'],
         'runner_build':tag.removeprefix('b'),'upstream':'HY-MT1.5-1.8B Q4_K_M / llama.cpp '+tag,
         'languages':recipe['languages'],'files':files,'model_revision':recipe['model']['revision'],
         'validation':{'standalone_windows':False,'frozen_application':False,'macos':False,'linux':False},
         'redistribution_review':False}]}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--recipe',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if sys.platform!='win32':parser.error('Prepare Windows profiles on Windows')
    prepare(args.output.resolve(),args.recipe)
