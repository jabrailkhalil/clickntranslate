"""Check shipped UI tables, action labels, hints and formatting before packaging."""
import argparse
import ast
import json
from pathlib import Path
import re
from collections import Counter
from string import Formatter

LOCALES=('en','ru','es','de','fr','zh','pt','it','ar','tr','hi','id')
TUPLE_FILES={'assistant_text.py','control_hints.py','dialog_text.py','dynamic_templates.py'}


def format_fields(value):
    return Counter((field,spec,conversion) for _,field,spec,conversion in Formatter().parse(value)
                   if field is not None)


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
    def check(table,source,rows):
        if not source:return
        tables.append(dict(id=table,source_messages=len(source)))
        for key,value in source.items():messages[table+':'+key]=value
        for locale in LOCALES[1:]:
            translated=rows.get(locale,{})
            for key,value in source.items():
                if key not in translated:
                    issues.append(dict(table=table,locale=locale,key=key,problem='missing'))
                    continue
                if value.strip() and not translated[key].strip():
                    issues.append(dict(table=table,locale=locale,key=key,problem='empty'))
                try:valid=format_fields(value)==format_fields(translated[key])
                except ValueError:valid=False
                if not valid:issues.append(dict(table=table,locale=locale,key=key,problem='placeholders'))
                if locale in LOCALES[6:] and re.findall(r'</?[A-Za-z][^>]*>',value)!=re.findall(r'</?[A-Za-z][^>]*>',translated[key]):
                    issues.append(dict(table=table,locale=locale,key=key,problem='markup'))
                if re.search(r'ZXQ\d|\[CNT\d',translated[key]):
                    issues.append(dict(table=table,locale=locale,key=key,problem='authoring-token'))
    for path in paths:
        tree=ast.parse(path.read_text(encoding='utf-8-sig'))
        parents={id(child):node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
        for node in ast.walk(tree):
            if not isinstance(node,(ast.Dict,ast.Tuple)):continue
            if path.name == 'languages.py' and isinstance(parents.get(id(node)), ast.Dict):
                continue
            table=f'{path.relative_to(root).as_posix()}:{node.lineno}'
            if isinstance(node,ast.Dict):
                rows={k.value:v for k,v in zip(node.keys,node.values) if isinstance(k,ast.Constant) and isinstance(k.value,str)}
                if 'en' in rows and 'ru' in rows:
                    check(table,strings(rows['en']),{locale:strings(value) for locale,value in rows.items()})
                elif 'ru' in rows and set(rows)&{'es','de','fr','zh'}:
                    call=parents.get(id(parents.get(id(node))))
                    if isinstance(call,ast.Call) and len(call.args)>1:
                        check(table,strings(call.args[1]),{locale:strings(value) for locale,value in rows.items()})
            elif isinstance(node,ast.Tuple) and path.name in TUPLE_FILES:
                try:values=ast.literal_eval(node)
                except (ValueError,TypeError):continue
                if (len(values) in (6,9,len(LOCALES)) and all(isinstance(value,str) for value in values)
                        and values not in (LOCALES,LOCALES[:9],LOCALES[:6])):
                    check(table,{'':values[0]},{locale:{'':value} for locale,value in zip(LOCALES,values)})
    return dict(tables=tables,messages=messages,issues=issues)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--templates',action='store_true',help='Also write draft templates for catalog migration')
    args=parser.parse_args();root=Path(__file__).resolve().parents[1]
    result=audit(root);args.output.mkdir(parents=True,exist_ok=True)
    (args.output/'audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    for locale,name in (('pt','Português'),('it','Italiano')) if args.templates else ():
        template=dict(locale=locale,native_name=name,status='draft',source_locale='en',
                      messages={key:'' for key in result['messages']})
        (args.output/f'{locale}.draft.json').write_text(json.dumps(template,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(tables=len(result['tables']),messages=len(result['messages']),issues=len(result['issues']))))
    return 1 if result['issues'] else 0


if __name__=='__main__':raise SystemExit(main())
