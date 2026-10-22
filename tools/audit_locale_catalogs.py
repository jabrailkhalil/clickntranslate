"""Extract literal UI language tables and check translations before packaging.

This is a migration audit, not a runtime translator. Generated templates do not
add unfinished languages to the application's language picker.
"""
import argparse
import ast
import json
from pathlib import Path
import re

LOCALES=('en','ru','es','de','fr','zh')


def strings(node, prefix=''):
    if isinstance(node,ast.Constant) and isinstance(node.value,str):
        return {prefix:node.value}
    result={}
    if isinstance(node,ast.Dict):
        children=((str(k.value),v) for k,v in zip(node.keys,node.values) if isinstance(k,ast.Constant))
    elif isinstance(node,(ast.List,ast.Tuple)):
        children=((str(i),v) for i,v in enumerate(node.elts))
    else:
        return result
    for key,value in children:
        result.update(strings(value,prefix+'.'+key if prefix else key))
    return result


def audit(root):
    tables=[];messages={};issues=[]
    paths=[root/'main.py',*sorted((root/'src').glob('*.py'))]
    for path in paths:
        tree=ast.parse(path.read_text(encoding='utf-8-sig'))
        for node in ast.walk(tree):
            if not isinstance(node,ast.Dict):continue
            rows={k.value:v for k,v in zip(node.keys,node.values) if isinstance(k,ast.Constant) and isinstance(k.value,str)}
            if not ('en' in rows and 'ru' in rows):continue
            source=strings(rows['en'])
            if not source:continue
            table=f'{path.relative_to(root).as_posix()}:{node.lineno}'
            tables.append(dict(id=table,source_messages=len(source)))
            for key,text in source.items():messages[table+':'+key]=text
            for locale in LOCALES[1:]:
                translated=strings(rows[locale]) if locale in rows else {}
                for key,text in source.items():
                    if key not in translated:
                        issues.append(dict(table=table,locale=locale,key=key,problem='missing'))
                    elif set(re.findall(r'\{[A-Za-z_]\w*\}',text)) != set(re.findall(r'\{[A-Za-z_]\w*\}',translated[key])):
                        issues.append(dict(table=table,locale=locale,key=key,problem='placeholders'))
    return dict(tables=tables,messages=messages,issues=issues)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();root=Path(__file__).resolve().parents[1]
    result=audit(root);args.output.mkdir(parents=True,exist_ok=True)
    (args.output/'audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    for locale,name in (('pt','Português'),('it','Italiano')):
        template=dict(locale=locale,native_name=name,status='draft',source_locale='en',
                      messages={key:'' for key in result['messages']})
        (args.output/f'{locale}.draft.json').write_text(json.dumps(template,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(tables=len(result['tables']),messages=len(result['messages']),issues=len(result['issues']))))


if __name__=='__main__':main()
