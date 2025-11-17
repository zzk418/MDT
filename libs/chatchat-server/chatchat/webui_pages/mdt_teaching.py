import base64
import uuid
from datetime import datetime
from typing import List, Dict
import json

import openai
import streamlit as st
import streamlit_antd_components as sac
from streamlit_chatbox import *
from streamlit_extras.bottom_container import bottom

from chatchat.settings import Settings
from chatchat.server.knowledge_base.utils import LOADER_DICT
from chatchat.server.utils import get_config_models, get_config_platforms, get_default_llm, api_address
from chatchat.webui_pages.dialogue.dialogue import (save_session, restore_session, rerun,
                                                    get_messages_history, upload_temp_docs,
                                                    add_conv, del_conv, clear_conv)
from chatchat.webui_pages.utils import *


chat_box = ChatBox(assistant_avatar=get_img_base64("chatchat_icon_blue_square_v2.png"))

# MDT教学案例数据
MDT_CASE_STUDIES = {
    "前列腺癌": [
        {
            "id": "prostate_001",
            "title": "晚期前列腺癌MDT诊疗案例",
            "description": "患者男性，68岁，因排尿困难、骨痛就诊，PSA显著升高",
            "difficulty": "高级",
            "tags": ["肿瘤", "多学科", "晚期"],
            "content": """
## 病例基本信息
- 患者：男性，68岁
- 主诉：排尿困难3个月，腰背部疼痛1个月
- 既往史：高血压10年，药物控制良好

## 检查结果
- PSA：85 ng/mL
- 直肠指检：前列腺质硬，表面结节感
- MRI：前列腺外周带T2低信号，侵犯精囊，盆腔淋巴结肿大
- 骨扫描：多发骨转移（脊柱、骨盆）

## 多学科讨论要点
1. 泌尿外科：是否需要前列腺穿刺活检？
2. 肿瘤内科：内分泌治疗方案选择
3. 放疗科：骨转移灶姑息放疗指征
4. 病理科：Gleason评分评估
5. 影像科：影像学分期准确性

## AI辅助分析
- 影像AI分析：前列腺癌侵犯范围评估
- 病理AI辅助：Gleason评分预测
- 治疗方案AI推荐：基于NCCN指南
"""
        },
        {
            "id": "prostate_002", 
            "title": "局限性前列腺癌治疗决策",
            "description": "患者65岁，体检发现PSA升高，MRI提示局限性病变",
            "difficulty": "中级",
            "tags": ["早期", "手术", "放疗"],
            "content": """
## 病例基本信息
- 患者：男性，65岁
- 主诉：体检发现PSA升高
- 家族史：父亲有前列腺癌病史

## 检查结果  
- PSA：12.5 ng/mL
- 直肠指检：前列腺右侧叶质硬
- MRI：右侧外周带结节，PI-RADS 4分
- 穿刺活检：Gleason 3+4=7分

## 治疗选择讨论
1. 根治性前列腺切除术
2. 外照射放疗
3. 近距离放疗
4. 主动监测

## AI决策支持
- 预后预测模型：10年生存率评估
- 并发症风险预测
- 生活质量影响分析
"""
        }
    ],
    "膀胱癌": [
        {
            "id": "bladder_001",
            "title": "肌层浸润性膀胱癌综合治疗",
            "description": "患者72岁，无痛性肉眼血尿，膀胱镜发现浸润性肿瘤",
            "difficulty": "高级", 
            "tags": ["浸润性", "根治术", "新辅助"],
            "content": """
## 病例基本信息
- 患者：男性，72岁
- 主诉：无痛性肉眼血尿2个月
- 吸烟史：40年，20支/天

## 检查结果
- 膀胱镜：右侧壁菜花样肿瘤，基底宽
- CTU：膀胱壁增厚，未见明确远处转移
- TURBT病理：高级别尿路上皮癌，浸润肌层

## MDT讨论重点
1. 新辅助化疗的必要性
2. 根治性膀胱切除术范围
3. 尿流改道方式选择
4. 术后辅助治疗

## AI辅助分析
- 病理图像AI分析：浸润深度评估
- 化疗敏感性预测
- 手术并发症风险评估
"""
        }
    ],
    "肾癌": [
        {
            "id": "kidney_001",
            "title": "复杂性肾肿瘤保留肾单位手术",
            "description": "患者45岁，体检发现右肾复杂肿瘤，希望保留肾功能",
            "difficulty": "高级",
            "tags": ["保留肾单位", "复杂性", "微创"],
            "content": """
## 病例基本信息  
- 患者：男性，45岁
- 主诉：体检发现右肾占位
- 肾功能：血肌酐正常

## 检查结果
- CT：右肾中极4.5cm肿瘤，R.E.N.A.L评分10分
- 三维重建：肿瘤紧邻集合系统

## 手术方案讨论
1. 腹腔镜肾部分切除术
2. 机器人辅助肾部分切除术  
3. 开放肾部分切除术
4. 根治性肾切除术

## AI手术规划
- 三维重建与手术路径规划
- 缺血时间预测
- 术后肾功能预测
"""
        }
    ]
}

# 教学评估标准
ASSESSMENT_CRITERIA = {
    "诊断准确性": {
        "权重": 0.3,
        "评分标准": ["完全准确", "基本准确", "部分准确", "不准确"]
    },
    "治疗方案合理性": {
        "权重": 0.4, 
        "评分标准": ["非常合理", "合理", "基本合理", "不合理"]
    },
    "多学科协作": {
        "权重": 0.2,
        "评分标准": ["优秀协作", "良好协作", "一般协作", "缺乏协作"]
    },
    "沟通表达能力": {
        "权重": 0.1,
        "评分标准": ["表达清晰", "表达基本清晰", "表达一般", "表达不清"]
    }
}

def init_mdt_widgets():
    """初始化MDT教学组件"""
    st.session_state.setdefault("selected_disease", "前列腺癌")
    st.session_state.setdefault("selected_case", None)
    st.session_state.setdefault("teaching_mode", "案例分析")
    st.session_state.setdefault("assessment_scores", {})
    st.session_state.setdefault("discussion_records", [])
    st.session_state.setdefault("cur_conv_name", chat_box.cur_chat_name)
    st.session_state.setdefault("last_conv_name", chat_box.cur_chat_name)


def mdt_teaching_page(api: ApiRequest):
    """MDT诊疗教学平台主页面"""
    ctx = chat_box.context
    ctx.setdefault("uid", uuid.uuid4().hex)
    ctx.setdefault("llm_model", get_default_llm())
    ctx.setdefault("temperature", Settings.model_settings.TEMPERATURE)
    init_mdt_widgets()

    # 会话切换处理
    if st.session_state.cur_conv_name != st.session_state.last_conv_name:
        save_session(st.session_state.last_conv_name)
        restore_session(st.session_state.cur_conv_name)
        st.session_state.last_conv_name = st.session_state.cur_conv_name

    # 侧边栏 - 教学资源管理
    with st.sidebar:
        st.header("🏥 AI+MDT诊疗教学平台")
        
        # 教学模式选择
        teaching_mode = st.radio(
            "选择教学模式：",
            ["案例分析", "虚拟仿真", "团队协作", "考核评估"],
            key="teaching_mode"
        )
        
        st.divider()
        
        # 病例选择
        st.subheader("📋 教学案例库")
        disease_type = st.selectbox(
            "选择疾病类型：",
            list(MDT_CASE_STUDIES.keys()),
            key="selected_disease"
        )
        
        cases = MDT_CASE_STUDIES[disease_type]
        case_options = {f"{case['title']} ({case['difficulty']})": case for case in cases}
        selected_case_title = st.selectbox(
            "选择教学案例：",
            list(case_options.keys()),
            key="selected_case_title"
        )
        
        if selected_case_title:
            selected_case = case_options[selected_case_title]
            st.session_state.selected_case = selected_case
            
            # 显示案例基本信息
            with st.expander("案例概览", expanded=True):
                st.write(f"**难度**: {selected_case['difficulty']}")
                st.write(f"**标签**: {', '.join(selected_case['tags'])}")
                st.write(f"**描述**: {selected_case['description']}")
                
                if st.button("开始案例分析", use_container_width=True):
                    # 清空对话历史，开始新的案例分析
                    chat_box.reset_history()
                    # 自动发送案例介绍
                    chat_box.user_say(f"开始分析案例：{selected_case['title']}")
                    chat_box.ai_say(f"让我们开始分析这个{selected_case['difficulty']}难度的{selected_case['title']}案例。请仔细阅读病例信息并提出您的诊断思路和治疗方案。")
        
        st.divider()
        
        # 会话管理
        st.subheader("💬 会话管理")
        cols = st.columns(3)
        conv_names = chat_box.get_chat_names()
        
        conversation_name = sac.buttons(
            conv_names,
            label="当前会话：",
            key="cur_conv_name",
        )
        chat_box.use_chat_name(conversation_name)
        
        if cols[0].button("新建", on_click=add_conv, use_container_width=True):
            ...
        if cols[1].button("重命名"):
            st.session_state.rename_dialog = True
        if cols[2].button("删除", on_click=del_conv, use_container_width=True):
            ...
        
        # 重命名对话框
        if st.session_state.get("rename_dialog"):
            with st.expander("重命名会话", expanded=True):
                new_name = st.text_input("新会话名称")
                col1, col2 = st.columns(2)
                if col1.button("确认"):
                    if new_name:
                        chat_box.change_chat_name(new_name)
                        restore_session()
                        st.session_state["cur_conv_name"] = new_name
                        st.session_state.rename_dialog = False
                        rerun()
                if col2.button("取消"):
                    st.session_state.rename_dialog = False

    # 主内容区域
    st.title("🤖 AI+MDT诊疗教学平台")
    
    # 根据教学模式显示不同内容
    if teaching_mode == "案例分析":
        display_case_analysis(selected_case if st.session_state.get("selected_case") else None)
    elif teaching_mode == "虚拟仿真":
        display_virtual_simulation()
    elif teaching_mode == "团队协作":
        display_team_collaboration()
    elif teaching_mode == "考核评估":
        display_assessment_evaluation()

    # 对话界面
    st.divider()
    st.subheader("💭 AI智能辅导")
    
    # 显示对话消息
    chat_box.output_messages()
    
    # 聊天输入
    with bottom():
        cols = st.columns([1, 15, 1])
        if cols[0].button("⚙️", help="模型配置"):
            show_model_config()
        if cols[2].button("🗑️", help="清空对话"):
            chat_box.reset_history()
            rerun()
        
        prompt = cols[1].chat_input("请输入您的问题或分析思路...", key="prompt")
    
    if prompt:
        handle_user_input(prompt, api)


def display_case_analysis(selected_case):
    """显示案例分析界面"""
    if not selected_case:
        st.info("请从侧边栏选择一个教学案例开始分析")
        return
    
    st.header(f"📊 案例分析：{selected_case['title']}")
    
    # 显示案例内容
    with st.expander("📖 病例详细信息", expanded=True):
        st.markdown(selected_case['content'])
    
    # 分析工具
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🩺 诊断思路分析", use_container_width=True):
            chat_box.user_say("请帮我分析这个病例的诊断思路")
            chat_box.ai_say("""
让我帮您分析这个病例的诊断思路：

1. **病史特点分析**：
   - 主要症状特征
   - 危险因素评估
   - 疾病进展速度

2. **检查结果解读**：
   - 关键指标意义
   - 影像学特征
   - 病理学表现

3. **鉴别诊断**：
   - 主要鉴别疾病
   - 排除标准
   - 确诊依据

请告诉我您对这个病例的具体疑问。
""")
    
    with col2:
        if st.button("💊 治疗方案讨论", use_container_width=True):
            chat_box.user_say("请讨论这个病例的治疗方案")
            chat_box.ai_say("""
让我们讨论治疗方案选择：

**多学科治疗选择**：
1. 外科治疗：手术适应症、术式选择
2. 内科治疗：药物选择、疗程安排  
3. 放疗治疗：适应症、技术选择
4. 综合治疗：多学科协作方案

**个体化考量**：
- 患者年龄和身体状况
- 肿瘤分期和分级
- 患者意愿和生活质量

请提出您对治疗方案的具体问题。
""")
    
    with col3:
        if st.button("🤝 MDT协作要点", use_container_width=True):
            chat_box.user_say("这个病例的MDT协作要点是什么？")
            chat_box.ai_say("""
这个病例的MDT协作要点包括：

**各学科角色**：
- 泌尿外科：手术决策和技术实施
- 肿瘤内科：系统治疗方案
- 放疗科：放射治疗规划
- 病理科：诊断确认和分级
- 影像科：分期评估和随访

**协作关键点**：
- 治疗时机协调
- 信息共享机制
- 决策共识建立
- 随访计划制定

请分享您的协作经验或疑问。
""")


def display_virtual_simulation():
    """显示虚拟仿真界面"""
    st.header("🔄 虚拟仿真训练")
    
    st.info("虚拟仿真功能正在开发中...")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("影像诊断模拟")
        if st.button("开始影像诊断训练", use_container_width=True):
            st.session_state.simulation_mode = "imaging"
            chat_box.user_say("开始影像诊断模拟训练")
            chat_box.ai_say("""
欢迎来到影像诊断模拟训练！

我将为您展示一系列泌尿系统影像学图像，请您：
1. 描述影像学表现
2. 提出诊断意见
3. 分析关键征象

准备好了吗？让我们开始第一个病例...
""")
    
    with col2:
        st.subheader("手术规划模拟")
        if st.button("开始手术规划训练", use_container_width=True):
            st.session_state.simulation_mode = "surgery"
            chat_box.user_say("开始手术规划模拟训练")
            chat_box.ai_say("""
欢迎来到手术规划模拟训练！

在这个训练中，您将：
1. 分析术前影像资料
2. 制定手术方案
3. 评估手术风险
4. 规划手术步骤

请准备好开始您的手术规划...
""")


def display_team_collaboration():
    """显示团队协作界面"""
    st.header("👥 团队协作项目")
    
    st.info("团队协作功能正在开发中...")
    
    # 模拟团队项目
    projects = [
        {"name": "复杂肾肿瘤MDT方案", "status": "进行中", "members": 4},
        {"name": "晚期前列腺癌综合治疗", "status": "已完成", "members": 5},
        {"name": "膀胱癌新辅助治疗", "status": "待开始", "members": 3}
    ]
    
    for project in projects:
        with st.expander(f"{project['name']} - {project['status']}"):
            st.write(f"团队成员：{project['members']}人")
            if project['status'] == "进行中":
                if st.button(f"加入{project['name']}", key=project['name']):
                    chat_box.user_say(f"我想加入团队项目：{project['name']}")
                    chat_box.ai_say(f"欢迎加入'{project['name']}'团队项目！在这个项目中，您将与其他{project['members']-1}位医师协作完成病例分析和治疗方案制定。")


def display_assessment_evaluation():
    """显示考核评估界面"""
    st.header("📝 学习成果评估")
    
    if not st.session_state.get("selected_case"):
        st.warning("请先选择一个教学案例进行学习")
        return
    
    selected_case = st.session_state.selected_case
    
    st.subheader("考核标准")
    for criterion, details in ASSESSMENT_CRITERIA.items():
        with st.expander(f"{criterion} (权重: {details['权重']*100}%)"):
            st.write("评分标准：")
            for i, standard in enumerate(details['评分标准']):
                st.write(f"{i+1}. {standard}")
    
    st.subheader("自我评估")
    scores = {}
    for criterion, details in ASSESSMENT_CRITERIA.items():
        score = st.select_slider(
            f"{criterion}评分",
            options=details['评分标准'],
            key=f"score_{criterion}"
        )
        # 修复类型错误：使用列表索引而不是字典索引
        score_options = details['评分标准']
        scores[criterion] = score_options.index(score) + 1
    
    if st.button("提交评估", use_container_width=True):
        total_score = 0
        for criterion, score in scores.items():
            weight = ASSESSMENT_CRITERIA[criterion]['权重']
            total_score += score * weight
        
        st.session_state.assessment_scores = scores
        st.session_state.total_score = total_score
        
        chat_box.user_say("我完成了自我评估")
        chat_box.ai_say(f"""
感谢您完成自我评估！

**评估结果总结**：
- 总分：{total_score:.2f}/4.00
- 各项评分：{json.dumps(scores, ensure_ascii=False)}

**学习建议**：
根据您的评估结果，我建议您：
1. 继续加强在治疗方案制定方面的训练
2. 多参与MDT讨论，提升协作能力
3. 定期复习相关指南和最新研究

您希望在哪些方面获得更多帮助？
""")


def show_model_config():
    """显示模型配置对话框"""
    with st.sidebar:
        with st.expander("⚙️ 模型配置", expanded=True):
            # 模型选择
            llm_models = get_config_models()
            current_model = st.session_state.get("llm_model", get_default_llm())
            selected_model = st.selectbox(
                "选择AI模型：",
                llm_models,
                index=llm_models.index(current_model) if current_model in llm_models else 0,
                key="llm_model_select"
            )
            
            # 温度设置
            temperature = st.slider(
                "创造性 (Temperature)：",
                min_value=0.0,
                max_value=1.0,
                value=st.session_state.get("temperature", 0.7),
                step=0.1,
                key="temperature_slider"
            )
            
            # 最大token数
            max_tokens = st.slider(
                "最大回复长度：",
                min_value=100,
                max_value=4000,
                value=2000,
                step=100,
                key="max_tokens"
            )
            
            if st.button("应用配置", use_container_width=True):
                st.session_state.llm_model = selected_model
                st.session_state.temperature = temperature
                st.success("模型配置已更新！")


def handle_user_input(prompt: str, api: ApiRequest):
    """处理用户输入并获取AI回复"""
    if not prompt.strip():
        return
    
    # 添加用户消息到对话历史
    chat_box.user_say(prompt)
    
    # 获取当前配置
    llm_model = st.session_state.get("llm_model", get_default_llm())
    temperature = st.session_state.get("temperature", Settings.model_settings.TEMPERATURE)
    
    try:
        # 构建消息历史
        history = get_messages_history(chat_box.history)
        
        # 获取AI回复
        text = ""
        chat_box.ai_say("正在思考中...")
        
        # 根据当前教学模式构建不同的提示词
        teaching_mode = st.session_state.get("teaching_mode", "案例分析")
        selected_case = st.session_state.get("selected_case")
        
        # 构建教学专用的系统提示
        system_prompt = build_teaching_system_prompt(teaching_mode, selected_case)
        
        # 调用API获取回复
        for chunk in api.chat_chat(
            query=prompt,
            history=history,
            stream=True,
            model_name=llm_model,
            temperature=temperature,
            max_tokens=2000,
            system_prompt=system_prompt
        ):
            if chunk:
                text += chunk
                chat_box.update_msg(text)
        
        # 保存会话
        save_session(chat_box.cur_chat_name)
        
    except Exception as e:
        chat_box.update_msg(f"抱歉，发生了错误：{str(e)}")
        st.error(f"API调用失败：{str(e)}")


def build_teaching_system_prompt(teaching_mode: str, selected_case: dict = None) -> str:
    """构建教学专用的系统提示词"""
    base_prompt = """你是一位经验丰富的泌尿外科专家和医学教育者，专门从事AI+MDT诊疗教学。请根据当前教学模式提供专业、准确的医学指导。"""
    
    if teaching_mode == "案例分析":
        if selected_case:
            case_info = f"""
当前分析案例：{selected_case['title']}
案例难度：{selected_case['difficulty']}
案例描述：{selected_case['description']}
"""
        else:
            case_info = "请先选择一个教学案例"
        
        return base_prompt + f"""
你正在指导住院医师进行案例分析教学。

{case_info}

请按照以下原则提供指导：
1. 鼓励学员独立思考，不要直接给出答案
2. 提供循证医学依据和最新指南推荐
3. 强调多学科协作的重要性
4. 指出常见的诊断和治疗误区
5. 结合病例特点进行个性化指导

用专业但友好的语气进行交流。
"""
    
    elif teaching_mode == "虚拟仿真":
        return base_prompt + """
你正在指导虚拟仿真训练。

请按照以下原则提供指导：
1. 模拟真实的临床场景和决策过程
2. 提供即时反馈和纠正
3. 强调操作规范和安全意识
4. 鼓励学员解释自己的决策思路
5. 提供替代方案和优化建议

保持训练的真实性和教育性。
"""
    
    elif teaching_mode == "团队协作":
        return base_prompt + """
你正在指导团队协作项目。

请按照以下原则提供指导：
1. 促进团队成员间的有效沟通
2. 帮助协调不同学科的观点
3. 强调团队决策的重要性
4. 提供协作技巧和最佳实践
5. 帮助解决团队冲突和分歧

扮演团队协调者和指导者的角色。
"""
    
    elif teaching_mode == "考核评估":
        return base_prompt + """
你正在指导学习成果评估。

请按照以下原则提供指导：
1. 提供客观、建设性的反馈
2. 指出学员的优势和改进空间
3. 基于考核标准提供具体建议
4. 帮助制定个性化的学习计划
5. 鼓励持续学习和专业发展

保持评估的公正性和教育价值。
"""
    
    else:
        return base_prompt
