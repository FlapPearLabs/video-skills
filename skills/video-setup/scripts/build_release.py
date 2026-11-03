#!/usr/bin/env python3
"""Build six independent WorkBuddy ZIPs plus separate development evidence. No upload or API calls."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import zipfile

import yaml

NAMES = ('video-setup','video-grill','video-to-spec','video-to-tickets','video-implement','video-diagnose')
SHARED = {'project-contract.md': NAMES,
          'quality.md': ('video-grill','video-to-spec','video-to-tickets','video-implement','video-diagnose'),
          'profiles.md': ('video-grill','video-to-spec'),
          'libtv.md': ('video-setup','video-implement','video-diagnose')}
LABELS = {
    'video-setup': ('视频环境检查','Video Setup','Inspect tools, project records, capabilities and recovery readiness.'),
    'video-grill': ('视频创意讨论','Video Grill','Discuss video intent and select visual directions from real references.'),
    'video-to-spec': ('视频制作规格','Video to Spec','Turn agreed video ideas into scripts, shot plans and acceptance criteria.'),
    'video-to-tickets': ('视频任务拆分','Video to Tickets','Split a video specification into dependency-aware production tickets.'),
    'video-implement': ('视频制作执行','Video Implement','Execute approved production tickets with recorded outputs and bounded spending.'),
    'video-diagnose': ('视频局部修复','Video Diagnose','Diagnose video defects and repair only the responsible production scope.')}
REQUIRED = ('name','display_name','display_name_en','description','description_zh','description_en','version','author')
RUNTIME_REFS = {'project-contract.md','quality.md','profiles.md','libtv.md','workbuddy-acceptance.md'}


def parse(text):
    match = re.match(r'\A---\r?\n(.*?)\r?\n---\r?\n', text, re.S)
    if not match:
        raise ValueError('missing YAML frontmatter')
    return yaml.safe_load(match.group(1)), text[match.end():]


def resolve(root):
    found = {}
    for md in Path(root).glob('*/SKILL.md'):
        meta,_ = parse(md.read_text(encoding='utf-8'))
        name = meta.get('name')
        if name in NAMES:
            if name in found:
                raise ValueError('duplicate skill: '+name)
            found[name] = md.parent
    if set(found) != set(NAMES):
        raise ValueError('six canonical skills must exist')
    return found


def shared_files(skills):
    source = skills['video-setup']
    for file, names in SHARED.items():
        origin = source/'references'/file
        for name in names:
            yield origin, skills[name]/'references'/file
    yield source/'scripts/project_files.py', skills['video-implement']/'scripts/project_files.py'


def sync(skills):
    for src,dst in shared_files(skills):
        if src != dst:
            shutil.copyfile(src,dst)


def check_shared(skills):
    for src,dst in shared_files(skills):
        if not dst.is_file() or src.read_bytes() != dst.read_bytes():
            raise ValueError('shared file drift: '+str(dst))


def adapt_md(text):
    text = text.replace('assets/','templates/')
    return re.sub(r'\[([^\]]+)\]\((references/[^)]+)\)', lambda m: m[1]+'（@'+m[2]+'）', text)


def runtime_entries(name, folder, version, author):
    meta,body = parse((folder/'SKILL.md').read_text(encoding='utf-8'))
    zh,en,description_en = LABELS[name]
    metadata = dict(name=name,display_name=zh,display_name_en=en,description=meta['description'],
                    description_zh=meta['description'],description_en=description_en,version=version,author=author)
    if name == 'video-setup':
        body = body.split('## 维护与真实验收')[0]
        body += ('\n## 导入后核对\n\n'
                 '在真实WorkBuddy中读取 @references/project-contract.md 的“明确局部修改的批准继承”小节，并报告三文件名；'
                 '以实际技能目录定位 scripts/project_files.py，仅先运行 --help。不能凭本正文复述冒充读到资源。'
                 '按 @references/workbuddy-acceptance.md 验收；未导入、资源未读或无回执均保持未验证。\n')
    entries = {'SKILL.md': ('---\n'+yaml.safe_dump(metadata,allow_unicode=True,sort_keys=False)+'---\n'+adapt_md(body)).encode()}
    for file in folder.rglob('*'):
        if not file.is_file():
            continue
        rel = file.relative_to(folder).as_posix()
        if rel.startswith('references/') and file.name in RUNTIME_REFS:
            entries[rel] = adapt_md(file.read_text(encoding='utf-8')).encode()
        elif rel.startswith('scripts/') and file.name in {'project_files.py','operation_guard.py'}:
            entries[rel] = file.read_bytes()
        elif rel.startswith('assets/') and file.suffix in {'.md','.json'}:
            entries[rel.replace('assets/','templates/',1)] = file.read_bytes()
    return entries


def validate_entries(name, entries):
    meta,body = parse(entries['SKILL.md'].decode())
    for field in REQUIRED:
        if not isinstance(meta.get(field),str) or not meta[field].strip():
            raise ValueError('missing WorkBuddy field: '+field)
    if meta['name'] != name or not re.fullmatch(r'\d+\.\d+\.\d+',meta['version']):
        raise ValueError('invalid name/version')
    for rel,data in entries.items():
        if rel.startswith('/') or '..' in Path(rel).parts:
            raise ValueError('unsafe entry')
        if rel.endswith('.md'):
            text=data.decode()
            if re.search(r'\]\(references/', text):
                raise ValueError('unadapted WorkBuddy reference')
            for ref in re.findall(r'@((?:references|scripts|templates)/[A-Za-z0-9_./-]+)',text):
                if ref not in entries:
                    raise ValueError('missing resource '+ref)
            for ref in re.findall(r'\]\(([^)]+)\)',text):
                if not ref.startswith(('http:','https:','#')) and ref not in entries:
                    raise ValueError('broken Markdown resource '+ref)
            for ref in re.findall(r'`((?:scripts|templates)/[A-Za-z0-9_./-]+)`',text):
                if ref not in entries:
                    raise ValueError('missing script/template '+ref)
        if b'feedbeeffeedbeeffeedbeeffeedbeef' in data.lower().replace(b'-',b''):
            raise ValueError('private smoke project leaked into runtime package')
        if rel.endswith('.py'):
            compile(data,rel,'exec')
    return True


def write_zip(path, entries, prefix=''):
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as archive:
        for rel,data in sorted(entries.items()):
            archive.writestr(prefix+rel,data)
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise ValueError('invalid ZIP')


def build(root, out, author, version='0.1.1', do_sync=False):
    skills=resolve(root)
    if do_sync:
        sync(skills)
    check_shared(skills)
    if not author.strip():
        raise ValueError('author is required')
    out=Path(out)
    out.mkdir(parents=True,exist_ok=True)
    runtime=out/'workbuddy'
    runtime.mkdir(exist_ok=True)
    manifest={'version':version,'format':'collection-of-single-skill-zips',
              'static_package_validation':'passed','workbuddy_import':'not_tested',
              'reference_runtime_loading':'not_tested','libtv_live_integration':'not_tested',
              'sources':['https://open.workbuddy.cn/docs/skill',
                         'https://www.workbuddy.cn/docs/workbuddy/From-Beginner-to-Expert-Guide/Function-Description/Skills-Market'],
              'skills':[]}
    for name in NAMES:
        entries=runtime_entries(name,skills[name],version,author)
        validate_entries(name,entries)
        file=runtime/(name+'-v'+version+'.zip')
        write_zip(file,entries,prefix=name+'/')
        manifest['skills'].append({'name':name,'file':file.name,'entries':len(entries),'sha256':hashlib.sha256(file.read_bytes()).hexdigest()})
    instructions=('Video Skills '+version+' · WorkBuddy安装集合\n\n'
        '外层ZIP是分发集合，不是单个Skill安装包。解压后进入workbuddy，先上传video-setup-v'+version+'.zip；'
        '在WorkBuddy技能→添加技能→上传技能中选择这个独立ZIP。通过资源读取检查后，再逐个上传其余五个ZIP。\n\n'
        '每个独立ZIP只有一个技能目录，内含SKILL.md和其全部运行资源；不要把六个ZIP一并当成一个Skill上传。\n'
        '先让Agent真实读取project-contract.md中的局部批准继承规则，再运行本技能project_files.py --help；'
        '没有真实回执不算验收通过。完整非生成/恢复清单在video-setup的references/workbuddy-acceptance.md。\n\n'
        '已做：元数据、引用、资源完整性、Python语法、ZIP结构的本地检查。'
        '未做：WorkBuddy客户端导入/资源实际加载、LibTV真实联调、视频生成、口型与商业交付验收。\n'
        '默认关闭未批准生成；原有可用预算内的明确局部修改继承批准，但不得增加金额、调用次数或素材范围。\n')
    collection={'INSTALL.md':instructions.encode(),'RELEASE.json':json.dumps(manifest,ensure_ascii=False,indent=2).encode()}
    for item in manifest['skills']:
        file=runtime/item['file']
        collection['workbuddy/'+file.name]=file.read_bytes()
    bundle=out/('Video-Skills-v'+version+'-WorkBuddy.zip')
    write_zip(bundle,collection)
    dev={}
    for name,folder in skills.items():
        for file in folder.rglob('*'):
            if file.is_file() and '__pycache__' not in file.parts:
                dev[name+'/'+file.relative_to(folder).as_posix()]=file.read_bytes()
    dev['RELEASE.json']=json.dumps({**manifest,'format':'development-source-six-skills',
                                   'runtime_bundle_name':bundle.name},ensure_ascii=False,indent=2).encode()
    development=out/('Video-Skills-v'+version+'-development.zip')
    write_zip(development,dev)
    return {'runtime_bundle':str(bundle),'development_bundle':str(development),'manifest':manifest}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skills-root',required=True)
    parser.add_argument('--out',required=True)
    parser.add_argument('--author',required=True)
    parser.add_argument('--version',default='0.1.1')
    parser.add_argument('--sync',action='store_true',help='copy shared canonical sources before building')
    args=parser.parse_args()
    print(json.dumps(build(args.skills_root,args.out,args.author,args.version,args.sync),ensure_ascii=False,indent=2))
