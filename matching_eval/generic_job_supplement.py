"""Codex-authored role blueprints for the remaining eight IT job families."""
from .generic_corpus import CORPUS, write_json

PROFILES = {
 '数据治理': ('数据治理工程师', ['盘点数据资产并核对字段口径','建设质量规则与异常追踪流程','维护元数据、血缘和业务术语映射'],
             'SQL、数据质量校验与元数据管理', '制造业主数据与供应链指标口径', '数据目录或血缘平台'),
 '本体实施': ('本体建模实施工程师', ['按业务方案配置对象、属性与关系','完成字段映射、数据清洗及实例导入','调试业务规则、查询与场景配置'],
             'SQL、Python或JavaScript及对象关系建模概念', '电力设备、工单和运行指标建模', '知识图谱、数据治理或Ontology平台'),
 'Python后端': ('Python后端工程师', ['实现业务接口与参数校验','优化数据库查询和异步任务','处理接口幂等、异常恢复与性能问题'],
             'Python、HTTP接口、关系数据库与自动化测试', '电商订单与库存协同', 'FastAPI、Django或消息队列'),
 'Java后端': ('Java后端工程师', ['实现领域服务与业务接口','维护事务、索引及缓存一致性','定位并发请求和服务依赖故障'],
             'Java、Spring、SQL及并发编程基础', '保险保单与理赔业务流程', '微服务治理或高并发系统'),
 '全栈': ('全栈开发工程师', ['交付前后端联动的业务功能','设计接口契约与数据模型','实现权限、测试与部署流程'],
             'JavaScript或TypeScript、一种后端语言及关系数据库', '企业内部审批与运营工作台', 'React、Vue或端到端测试'),
 '前端': ('前端开发工程师', ['实现组件化页面与状态管理','对接接口并处理异步和错误状态','优化加载性能、可访问性与交互一致性'],
             'HTML、CSS、JavaScript或TypeScript及浏览器调试', '实时设备监控与复杂数据可视化', 'React、Vue或前端性能分析'),
 '测试开发': ('测试开发工程师', ['分析需求并设计风险驱动测试用例','开发接口与集成自动化测试','定位失败原因并维护持续集成质量检查'],
             'Python或Java、接口测试、SQL及测试数据设计', '支付结算与账务对账', '性能测试、故障注入或测试平台'),
 '云平台运维': ('云平台运维工程师', ['维护Linux服务与容器部署','建设监控告警和故障排查流程','执行容量评估、备份恢复及发布回滚'],
             'Linux、网络基础、Docker及一种脚本语言', '多地域业务服务与灾备演练', 'Kubernetes、基础设施即代码或可观测性平台')}


def author_remaining():
    for offset, directions in [(12,list(PROFILES)[:4]),(16,list(PROFILES)[4:])]:
        path=CORPUS/f'authoring/jobs_{offset:02d}.json'
        if path.exists():
            continue
        jobs=[]
        for direction in directions:
            role,tasks,skills,industry,bonus=PROFILES[direction]
            variants=[
              ('初级'+role, f'在既定方案和代码规范下{tasks[0]}，协助{tasks[1]}，记录测试结果并修复可复现问题。',
               f'掌握{skills}的基础，能够阅读现有实现并完成一个可展示的小型项目；可以是课程、实习或个人项目，不设工作年限门槛。',
               '重点考察学习、调试和按规范完成任务的能力，暂不要求独立承担系统架构。'),
              (role, f'独立{tasks[0]}，持续{tasks[1]}，配合{tasks[2]}；与产品和相关工程团队澄清需求，按迭代交付可验证的成果。',
               f'具备两年以上相关项目实践，熟悉{skills}，能说明个人承担的实现、调试和验证工作，并处理常见线上或实施问题。',
               '需要能独立负责一个模块，记录边界条件、测试依据和未解决问题。'),
              ('高级'+role, f'负责复杂场景下{tasks[1]}与{tasks[2]}，制定技术方案、回归验证和演进计划，指导团队分析跨模块问题。',
               f'具备五年以上相关经验，熟练应用{skills}；有独立承担复杂系统或大型项目关键模块的证据，能够解释可靠性、成本与维护性的取舍。',
               '需要参与技术评审并形成可落地方案；仅有项目管理经历而无技术实践不能替代该要求。'),
              (industry+'方向'+role, f'围绕{industry}的业务场景{tasks[0]}，并{tasks[2]}；与业务人员核对流程、边界条件和结果，推动问题闭环。',
               f'熟悉{skills}，具有两年以上相关开发或实施经验，能够将业务约束转化为实现和验收用例，并解释数据或流程异常的定位方法。',
               '相关行业经验为优先项，不把行业名称不同视为直接不合格；实际任务经验应有可迁移性。'),
              (role+'（平台交付）', f'将{tasks[0]}与{tasks[1]}沉淀为可复用的平台能力，负责环境配置、权限、日志及部署验证，协助不同业务团队接入。',
               f'具备三年以上相关工程经验，熟悉{skills}，有部署、集成调试或跨团队交付实践；能够编写运行说明、测试脚本和故障排查步骤。',
               '交付须覆盖正常与异常路径，支持版本回滚和验收记录；是否出差由项目双方另行沟通确认。')]
            for index,(title,duties,requirements,scope) in enumerate(variants,1):
                text=f'职位名称：{title}。实际职责：{duties}必备能力：{requirements}{scope}优先条件：具有{bonus}相关实践，能提供清晰的项目说明与技术复盘。'
                jobs.append({'direction':direction,'variant':index,'title':title,'text':text})
        write_json(path,{'authoring_method':'Codex-authored role blueprints and responsibility variants','jobs':jobs})


if __name__=='__main__':
    author_remaining()
