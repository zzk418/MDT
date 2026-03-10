import base64
import hashlib
import io
import json
import os
import uuid
from datetime import datetime
from PIL import Image as PILImage
from typing import Dict, List
from urllib.parse import urlencode

import httpx
import openai
import streamlit as st
import streamlit_antd_components as sac
from streamlit_chatbox import *
from streamlit_extras.bottom_container import bottom
from streamlit_paste_button import paste_image_button

from chatchat.settings import Settings
from langchain_chatchat.callbacks.agent_callback_handler import AgentStatus
from chatchat.server.knowledge_base.model.kb_document_model import DocumentWithVSId
from chatchat.server.knowledge_base.utils import format_reference
from chatchat.server.utils import MsgType, get_config_models, get_config_platforms, get_default_llm, api_address
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


def save_session(conv_name: str = None):
    """save session state to chat context"""
    chat_box.context_from_session(
        conv_name, exclude=["selected_page", "prompt", "cur_conv_name", "upload_image"]
    )


def restore_session(conv_name: str = None):
    """restore sesstion state from chat context"""
    chat_box.context_to_session(
        conv_name, exclude=["selected_page", "prompt", "cur_conv_name", "upload_image"]
    )


def rerun():
    """
    save chat context before rerun
    """
    save_session()
    st.rerun()


def get_messages_history(
    history_len: int, content_in_expander: bool = False
) -> List[Dict]:
    """
    返回消息历史。
    content_in_expander控制是否返回expander元素中的内容，一般导出的时候可以选上，传入LLM的history不需要
    """

    def filter(msg):
        content = [
            x for x in msg["elements"] if x._output_method in ["markdown", "text"]
        ]
        if not content_in_expander:
            content = [x for x in content if not x._in_expander]
        content = [x.content for x in content]

        return {
            "role": msg["role"],
            "content": "\n\n".join(content),
        }

    messages = chat_box.filter_history(history_len=history_len, filter=filter)
    if sys_msg := chat_box.context.get("system_message"):
        messages = [{"role": "system", "content": sys_msg}] + messages

    return messages


@st.cache_data
def upload_temp_docs(files, _api: ApiRequest) -> str:
    """
    将文件上传到临时目录，用于文件对话
    返回临时向量库ID
    """
    return _api.upload_temp_docs(files).get("data", {}).get("id")


@st.cache_data
def upload_image_file(file_name: str, content: bytes) -> dict:
    '''upload image for vision model using openai sdk'''
    client = openai.Client(base_url=f"{api_address()}/v1", api_key="NONE", http_client=httpx.Client(trust_env=False))
    return client.files.create(file=(file_name, content), purpose="assistants").to_dict()


def get_image_file_url(upload_file: dict) -> str:
    file_id = upload_file.get("id")
    return f"{api_address(True)}/v1/files/{file_id}/content"


def add_conv(name: str = ""):
    conv_names = chat_box.get_chat_names()
    if not name:
        i = len(conv_names) + 1
        while True:
            name = f"会话{i}"
            if name not in conv_names:
                break
            i += 1
    if name in conv_names:
        sac.alert(
            "创建新会话出错",
            f"该会话名称 \"{name}\" 已存在",
            color="error",
            closable=True,
        )
    else:
        chat_box.use_chat_name(name)
        st.session_state["cur_conv_name"] = name


def del_conv(name: str = None):
    conv_names = chat_box.get_chat_names()
    name = name or chat_box.cur_chat_name

    if len(conv_names) == 1:
        sac.alert(
            "删除会话出错", f"这是最后一个会话，无法删除", color="error", closable=True
        )
    elif not name or name not in conv_names:
        sac.alert(
            "删除会话出错", f"无效的会话名称：\"{name}\"", color="error", closable=True
        )
    else:
        chat_box.del_chat_name(name)
        # restore_session()
    st.session_state["cur_conv_name"] = chat_box.cur_chat_name


def clear_conv(name: str = None):
    chat_box.reset_history(name=name or None)


def init_mdt_widgets():
    """初始化MDT教学组件"""
    st.session_state.setdefault("selected_disease", "前列腺癌")
    st.session_state.setdefault("selected_case", None)
    st.session_state.setdefault("teaching_mode", "案例分析")
    st.session_state.setdefault("assessment_scores", {})
    st.session_state.setdefault("discussion_records", [])
    st.session_state.setdefault("cur_conv_name", chat_box.cur_chat_name)
    st.session_state.setdefault("last_conv_name", chat_box.cur_chat_name)


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
            st.session_state["pending_prompt"] = f"请详细分析病例「{selected_case['title']}」的诊断思路，包括：病史特点、关键检查结果解读、鉴别诊断要点以及最终诊断依据。"
            st.rerun()

    with col2:
        if st.button("💊 治疗方案讨论", use_container_width=True):
            st.session_state["pending_prompt"] = f"请针对病例「{selected_case['title']}」讨论多学科治疗方案，包括：各学科治疗选择、个体化考量因素、治疗优先级排序以及当前循证医学证据支持。"
            st.rerun()

    with col3:
        if st.button("🤝 MDT协作要点", use_container_width=True):
            st.session_state["pending_prompt"] = f"请分析病例「{selected_case['title']}」的MDT协作要点，包括：各参与学科的职责分工、关键决策节点、信息共享机制以及协作中的难点和注意事项。"
            st.rerun()


def display_virtual_simulation():
    """显示虚拟仿真界面"""
    st.header("🔄 虚拟仿真训练")

    selected_case = st.session_state.get("selected_case")
    case_title = selected_case["title"] if selected_case else "当前选中案例"

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("🖼️ 影像诊断模拟")
        st.caption("模拟阅片过程，训练影像学判断能力")
        if st.button("开始影像诊断训练", use_container_width=True):
            st.session_state.simulation_mode = "imaging"
            st.session_state["pending_prompt"] = (
                f"请模拟一个泌尿系统影像诊断训练场景（基于病例：{case_title}）。"
                "以考官身份，先描述影像学表现（不要直接给出结论），引导我逐步分析关键征象，"
                "提出问题让我判断影像学诊断，并在我回答后给出点评和指导。"
            )
            st.rerun()

    with col2:
        st.subheader("🔪 手术规划模拟")
        st.caption("模拟术前讨论，训练手术方案制定能力")
        if st.button("开始手术规划训练", use_container_width=True):
            st.session_state.simulation_mode = "surgery"
            st.session_state["pending_prompt"] = (
                f"请模拟一个手术规划讨论场景（基于病例：{case_title}）。"
                "以主治医师身份，引导我完成：1）术前影像评估；2）手术入路选择；"
                "3）术中风险预判；4）备选方案制定。逐步提问，根据我的回答给出专业反馈。"
            )
            st.rerun()

    st.divider()
    st.subheader("🏥 MDT会议模拟")
    st.caption("模拟多学科会诊讨论，训练协作沟通能力")
    col3, col4 = st.columns(2)
    with col3:
        if st.button("模拟MDT病例讨论", use_container_width=True):
            st.session_state["pending_prompt"] = (
                f"请模拟一次多学科会诊（MDT）讨论（病例：{case_title}）。"
                "你扮演MDT会议主持人，依次让我代表泌尿外科、肿瘤内科、放疗科、病理科、影像科发言，"
                "评价各学科意见的合理性，并引导团队形成最终诊疗共识。"
            )
            st.rerun()
    with col4:
        if st.button("模拟术后并发症处理", use_container_width=True):
            st.session_state["pending_prompt"] = (
                f"请模拟一个术后并发症处理场景（基于病例：{case_title}的治疗阶段）。"
                "描述一种可能出现的术后并发症，提问我如何识别和处理，"
                "根据我的回答给出临床指导意见，强调多学科协作处理要点。"
            )
            st.rerun()


def display_team_collaboration():
    """显示团队协作界面"""
    st.header("👥 团队协作项目")

    selected_case = st.session_state.get("selected_case")
    case_title = selected_case["title"] if selected_case else "当前选中案例"

    st.subheader("🗣️ 角色扮演协作")
    st.caption("选择你在MDT团队中扮演的专科角色，与AI协作完成病例讨论")

    role_options = ["泌尿外科医师", "肿瘤内科医师", "放疗科医师", "病理科医师", "影像科医师", "护理团队"]
    selected_role = st.selectbox("选择你的角色", role_options, key="team_role")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("开始角色扮演讨论", use_container_width=True):
            st.session_state["pending_prompt"] = (
                f"我将扮演{selected_role}参与病例「{case_title}」的MDT讨论。"
                f"请你扮演其他学科的专家（包括与{selected_role}不同的学科），"
                f"轮流向我提出需要{selected_role}解答的专科问题，并对我的回答给出跨学科视角的点评，"
                "帮助我理解其他学科的关注点和协作要点。"
            )
            st.rerun()
    with col2:
        if st.button("多学科意见综合", use_container_width=True):
            st.session_state["pending_prompt"] = (
                f"针对病例「{case_title}」，请分别从泌尿外科、肿瘤内科、放疗科、病理科、影像科"
                "五个专科角度，各自提出2-3个关键意见和关注点，"
                "然后帮助分析各学科意见的异同，并给出综合的MDT诊疗建议。"
            )
            st.rerun()

    st.divider()
    st.subheader("💡 协作技能训练")
    col3, col4 = st.columns(2)
    with col3:
        if st.button("沟通技巧训练", use_container_width=True):
            st.session_state["pending_prompt"] = (
                f"请针对病例「{case_title}」设计一个医患沟通场景训练。"
                "你扮演患者或家属，我来练习如何向非医疗背景的患者解释MDT诊疗方案，"
                "评估我的沟通是否清晰、有同理心，并给出改进建议。"
            )
            st.rerun()
    with col4:
        if st.button("学科间分歧处理", use_container_width=True):
            st.session_state["pending_prompt"] = (
                f"请模拟病例「{case_title}」MDT讨论中出现学科意见分歧的场景。"
                "设定两个学科对治疗方案有明显分歧，引导我分析分歧原因、寻找共同点，"
                "练习如何在尊重各学科专业判断的基础上达成团队共识。"
            )
            st.rerun()


def display_assessment_evaluation():
    """显示考核评估界面"""
    st.header("📝 学习成果评估")
    
    if not st.session_state.get("selected_case"):
        st.info("请先选择一个教学案例进行考核评估")
        return
    
    selected_case = st.session_state.selected_case
    
    # 显示案例信息
    with st.expander("📋 考核案例信息", expanded=True):
        st.markdown(f"**案例标题**: {selected_case['title']}")
        st.markdown(f"**案例难度**: {selected_case['difficulty']}")
        st.markdown(f"**案例描述**: {selected_case['description']}")
    
    # 考核评分表
    st.subheader("📊 考核评分")
    
    assessment_scores = st.session_state.get("assessment_scores", {})
    
    for criterion, details in ASSESSMENT_CRITERIA.items():
        col1, col2 = st.columns([2, 3])
        with col1:
            st.markdown(f"**{criterion}** (权重: {details['权重']})")
        with col2:
            score = st.select_slider(
                f"{criterion}评分",
                options=details["评分标准"],
                value=assessment_scores.get(criterion, details["评分标准"][1]),
                key=f"assessment_{criterion}"
            )
            assessment_scores[criterion] = score
    
    st.session_state.assessment_scores = assessment_scores
    
    # 计算总分
    if st.button("📈 计算总分并获取AI反馈", use_container_width=True):
        total_score = 0
        score_details = []
        for criterion, details in ASSESSMENT_CRITERIA.items():
            score_index = details["评分标准"].index(assessment_scores[criterion])
            normalized_score = (len(details["评分标准"]) - score_index - 1) / (len(details["评分标准"]) - 1)
            weighted_score = normalized_score * details["权重"] * 100
            total_score += weighted_score
            score_details.append(f"- {criterion}：{assessment_scores[criterion]}（权重{details['权重']}）")

        st.success(f"**总分: {total_score:.1f}/100**")

        score_summary = "\n".join(score_details)
        st.session_state["pending_prompt"] = (
            f"请对以下考核结果提供详细的专业反馈：\n\n"
            f"考核案例：{selected_case['title']}（难度：{selected_case['difficulty']}）\n"
            f"总分：{total_score:.1f}/100\n\n"
            f"各维度评分：\n{score_summary}\n\n"
            "请从以下角度给出建设性反馈：\n"
            "1. 各维度表现分析（优势与不足）\n"
            "2. 针对薄弱环节的具体改进建议\n"
            "3. 个性化的下一步学习计划\n"
            "4. 推荐的相关学习资源或训练方向"
        )
        st.rerun()
    
    # 讨论记录
    st.subheader("💬 讨论记录")
    
    discussion_records = st.session_state.get("discussion_records", [])
    
    for i, record in enumerate(discussion_records):
        with st.expander(f"讨论记录 {i+1}: {record.get('topic', '未命名')}"):
            st.markdown(f"**时间**: {record.get('time', '未知')}")
            st.markdown(f"**主题**: {record.get('topic', '未指定')}")
            st.markdown(f"**内容**: {record.get('content', '无内容')}")
    
    # 添加新讨论记录
    with st.form("new_discussion"):
        topic = st.text_input("讨论主题")
        content = st.text_area("讨论内容")
        
        if st.form_submit_button("📝 添加讨论记录"):
            new_record = {
                "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "topic": topic,
                "content": content
            }
            discussion_records.append(new_record)
            st.session_state.discussion_records = discussion_records
            st.rerun()
    
    # 导出考核报告
    if st.button("📄 生成考核报告", use_container_width=True):
        score_details = "\n".join([
            f"- **{criterion}**: {assessment_scores.get(criterion, ASSESSMENT_CRITERIA[criterion]['评分标准'][1])} (权重: {ASSESSMENT_CRITERIA[criterion]['权重']})"
            for criterion in ASSESSMENT_CRITERIA
        ])
        st.session_state["pending_prompt"] = (
            f"请帮我生成一份完整的MDT教学考核评估报告，格式规范，内容专业。\n\n"
            f"基本信息：\n"
            f"- 考核时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
            f"- 考核案例：{selected_case['title']}\n"
            f"- 案例难度：{selected_case['difficulty']}\n\n"
            f"考核评分结果：\n{score_details}\n\n"
            "报告应包含：考核概述、各维度详细评价、综合评分分析、专业发展建议（短期/中期/长期目标）、"
            "以及对该学员MDT能力培养的总体意见。报告最后注明由AI教学系统生成。"
        )
        st.rerun()


def mdt_teaching_page(api: ApiRequest, is_lite: bool = False):
    """MDT教学主页面"""
    ctx = chat_box.context
    ctx.setdefault("uid", uuid.uuid4().hex)
    ctx.setdefault("llm_model", get_default_llm())
    ctx.setdefault("temperature", Settings.model_settings.TEMPERATURE)
    st.session_state.setdefault("cur_conv_name", chat_box.cur_chat_name)
    st.session_state.setdefault("last_conv_name", chat_box.cur_chat_name)

    # 会话管理
    if st.session_state.cur_conv_name != st.session_state.last_conv_name:
        save_session(st.session_state.last_conv_name)
        restore_session(st.session_state.cur_conv_name)
        st.session_state.last_conv_name = st.session_state.cur_conv_name

    # 初始化MDT教学组件
    init_mdt_widgets()

    @st.experimental_dialog("模型配置", width="large")
    def llm_model_setting():
        """模型配置对话框"""
        cols = st.columns(3)
        platforms = ["所有"] + list(get_config_platforms())
        platform = cols[0].selectbox("选择模型平台", platforms, key="platform")
        platform_name_for_api = None if platform == "所有" else platform
        llm_models = list(
            get_config_models(
                model_type="llm", platform_name=platform_name_for_api
            )
        )
        llm_model = cols[1].selectbox("选择LLM模型", llm_models, key="llm_model")
        temperature = cols[2].slider("Temperature", 0.0, 1.0, key="temperature")
        system_message = st.text_area("System Message:", key="system_message")
        if st.button("确定"):
            rerun()

    @st.experimental_dialog("重命名会话")
    def rename_conversation():
        """重命名会话对话框"""
        name = st.text_input("会话名称")
        if st.button("确定"):
            chat_box.change_chat_name(name)
            restore_session()
            st.session_state["cur_conv_name"] = name
            rerun()

    # 侧边栏
    with st.sidebar:
        st.header("🏥 MDT教学系统")
        
        # 教学模式选择
        teaching_mode = st.radio(
            "选择教学模式",
            ["案例分析", "虚拟仿真", "团队协作", "考核评估"],
            key="teaching_mode"
        )
        
        # 疾病类型选择
        disease_type = st.selectbox(
            "选择疾病类型",
            list(MDT_CASE_STUDIES.keys()),
            key="selected_disease"
        )
        
        # 案例选择
        cases = MDT_CASE_STUDIES[disease_type]
        case_options = {case["title"]: case for case in cases}
        selected_case_title = st.selectbox(
            "选择教学案例",
            list(case_options.keys()),
            key="selected_case_title"
        )
        
        if selected_case_title:
            st.session_state.selected_case = case_options[selected_case_title]
        
        st.divider()
        
        # 会话管理
        st.subheader("💬 会话管理")
        conv_names = chat_box.get_chat_names()
        
        def on_conv_change():
            save_session(st.session_state.last_conv_name)
            restore_session(st.session_state.cur_conv_name)
            st.session_state.last_conv_name = st.session_state.cur_conv_name
        
        conversation_name = sac.buttons(
            conv_names,
            label="当前会话：",
            key="cur_conv_name",
        )
        chat_box.use_chat_name(conversation_name)
        
        col1, col2, col3 = st.columns(3)
        if col1.button("新建", use_container_width=True, on_click=add_conv):
            pass
        if col2.button("重命名", use_container_width=True):
            rename_conversation()
        if col3.button("删除", use_container_width=True, on_click=del_conv):
            pass
        
        st.divider()

        # 知识库关联
        st.subheader("📚 知识库关联")
        kb_list = ["不使用知识库"] + [x["kb_name"] for x in api.list_knowledge_bases()]
        selected_kb = st.selectbox(
            "关联知识库",
            kb_list,
            key="mdt_selected_kb",
            help="选择知识库后，对话将结合知识库内容进行回答"
        )
        if selected_kb != "不使用知识库":
            kb_top_k = st.number_input("匹配知识条数", 1, 20, value=3, key="mdt_kb_top_k")
            score_threshold = st.slider("匹配分数阈值", 0.0, 2.0, value=1.0, step=0.01, key="mdt_score_threshold")

        st.divider()

        # 对话轮数配置
        history_len = st.number_input("多轮对话保留轮数", 0, 20, value=5, key="mdt_history_len")

        st.divider()

        # 模型配置（内联展示，直接可切换）
        st.subheader("🤖 模型配置")
        all_platforms = list(get_config_platforms())
        # 默认优先选择 cloud-api 平台
        default_platform_idx = next(
            (i for i, p in enumerate(all_platforms) if p == "cloud-api"), 0
        )
        selected_platform = st.selectbox(
            "模型平台",
            all_platforms,
            index=default_platform_idx,
            key="platform",
        )
        llm_models = list(get_config_models(model_type="llm", platform_name=selected_platform))
        # 默认使用该平台第一个模型（cloud-api 只有一个）
        default_model = ctx.get("llm_model", get_default_llm())
        default_model_idx = next(
            (i for i, m in enumerate(llm_models) if m == default_model), 0
        )
        selected_llm = st.selectbox(
            "LLM 模型",
            llm_models,
            index=default_model_idx,
            key="llm_model",
        )
        ctx["llm_model"] = selected_llm
        st.caption(f"当前: `{selected_llm}`")

        if st.button("⚙️ 高级配置", use_container_width=True):
            widget_keys = ["platform", "llm_model", "temperature", "system_message"]
            chat_box.context_to_session(include=widget_keys)
            llm_model_setting()

        # 系统提示词显示
        with st.expander("📋 当前系统提示词"):
            system_prompt = build_teaching_system_prompt(
                teaching_mode,
                st.session_state.get("selected_case")
            )
            st.text_area("系统提示词", system_prompt, height=200, disabled=True)
    
    # 主内容区域
    st.title("🤖 AI+MDT诊疗教学系统")
    
    # 根据教学模式显示对应界面
    selected_case = st.session_state.get("selected_case")
    
    if teaching_mode == "案例分析":
        display_case_analysis(selected_case)
    elif teaching_mode == "虚拟仿真":
        display_virtual_simulation()
    elif teaching_mode == "团队协作":
        display_team_collaboration()
    elif teaching_mode == "考核评估":
        display_assessment_evaluation()
    
    # 显示聊天框
    chat_box.output_messages()
    
    # 聊天输入区域
    with bottom():
        cols = st.columns([1, 15, 1])
        
        if cols[0].button("🗑️", help="清空对话"):
            chat_box.reset_history()
            rerun()
        
        # 构建系统提示词
        system_prompt = build_teaching_system_prompt(teaching_mode, selected_case)
        chat_box.context["system_message"] = system_prompt
        
        prompt = cols[1].chat_input(
            f"请输入您的问题（当前模式：{teaching_mode}）",
            key="prompt"
        )
        
        if cols[2].button("📤", help="导出记录"):
            now = datetime.now()
            export_data = "".join(chat_box.export2md())
            cols[2].download_button(
                "导出",
                export_data,
                file_name=f"{now:%Y-%m-%d %H.%M}_MDT教学记录.md",
                mime="text/markdown",
                use_container_width=True,
            )
    
    # 处理pending_prompt（由按钮触发的快捷提问）
    pending_prompt = st.session_state.pop("pending_prompt", None)
    active_prompt = pending_prompt or prompt

    if active_prompt:
        selected_kb = st.session_state.get("mdt_selected_kb", "不使用知识库")
        kb_top_k = st.session_state.get("mdt_kb_top_k", 3)
        score_threshold = st.session_state.get("mdt_score_threshold", 1.0)
        configured_history_len = st.session_state.get("mdt_history_len", 5)

        history = get_messages_history(configured_history_len)

        # 系统提示注入历史（若历史为空则添加）
        system_msg = {"role": "system", "content": build_teaching_system_prompt(teaching_mode, selected_case)}
        messages = [system_msg] + history + [{"role": "user", "content": active_prompt}]

        chat_box.user_say(active_prompt)

        api_url = api_address(is_public=True)
        use_kb = selected_kb and selected_kb != "不使用知识库"

        if use_kb:
            client = openai.Client(
                base_url=f"{api_url}/knowledge_base/local_kb/{selected_kb}",
                api_key="NONE",
                timeout=100000,
                http_client=httpx.Client(trust_env=False),
            )
            chat_box.ai_say([
                Markdown("...", in_expander=True, title=f"知识库「{selected_kb}」匹配结果", state="running"),
                f"正在查询知识库 `{selected_kb}`，请稍候...",
            ])
            extra_body = dict(
                top_k=kb_top_k,
                score_threshold=score_threshold,
                temperature=ctx.get("temperature"),
                prompt_name="default",
                return_direct=False,
            )
            params = dict(
                messages=messages,
                model=ctx.get("llm_model"),
                stream=True,
                extra_body=extra_body,
            )
            text = ""
            docs_text = ""
            started = False
            try:
                for d in client.chat.completions.create(**params):
                    metadata = {"message_id": getattr(d, "message_id", "")}
                    if not started:
                        chat_box.update_msg("", element_index=1, streaming=False)
                        started = True
                    if hasattr(d, "docs"):
                        docs_text = d.docs
                        chat_box.update_msg(
                            docs_text, element_index=0, streaming=False, state="complete"
                        )
                    else:
                        text += d.choices[0].delta.content or ""
                        chat_box.update_msg(
                            text.replace("\n", "\n\n"), element_index=1, streaming=True, metadata=metadata
                        )
                chat_box.update_msg(text.replace("\n", "\n\n"), element_index=1, streaming=False)
            except Exception as e:
                st.error(str(e))
                chat_box.update_msg(f"抱歉，处理请求时出现错误：{str(e)}", element_index=1, streaming=False)
        else:
            # 普通对话（多轮，含系统提示）
            llm_model_config = Settings.model_settings.LLM_MODEL_CONFIG
            chat_model_config = {key: {} for key in llm_model_config.keys()}
            for key in llm_model_config:
                if c := llm_model_config[key]:
                    model = c.get("model", "").strip() or get_default_llm()
                    chat_model_config[key][model] = llm_model_config[key]
            llm_model = ctx.get("llm_model")
            if llm_model is not None:
                chat_model_config["llm_model"][llm_model] = llm_model_config["llm_model"].get(
                    llm_model, {}
                )

            chat_box.ai_say("正在思考...")
            text = ""
            started = False

            client = openai.Client(
                base_url=f"{api_address()}/chat",
                api_key="NONE",
                timeout=100000,
                http_client=httpx.Client(trust_env=False),
            )

            extra_body = dict(
                chat_model_config=chat_model_config,
                conversation_id=chat_box.context["uid"],
            )

            params = dict(
                messages=messages,
                model=ctx.get("llm_model"),
                stream=True,
                extra_body=extra_body,
            )

            if Settings.model_settings.MAX_TOKENS:
                params["max_tokens"] = Settings.model_settings.MAX_TOKENS

            try:
                for d in client.chat.completions.create(**params):
                    message_id = d.message_id
                    metadata = {"message_id": message_id}

                    if not started:
                        chat_box.update_msg("", streaming=False)
                        started = True

                    if d.status == AgentStatus.error:
                        st.error(d.choices[0].delta.content)
                    elif d.status == AgentStatus.llm_new_token:
                        text += d.choices[0].delta.content or ""
                        chat_box.update_msg(
                            text.replace("\n", "\n\n"), streaming=True, metadata=metadata
                        )
                    elif d.status == AgentStatus.llm_end:
                        text += d.choices[0].delta.content or ""
                        chat_box.update_msg(
                            text.replace("\n", "\n\n"), streaming=False, metadata=metadata
                        )
                    elif d.status is None:  # 非Agent聊天
                        text += d.choices[0].delta.content or ""
                        chat_box.update_msg(
                            text.replace("\n", "\n\n"), streaming=True, metadata=metadata
                        )

                chat_box.update_msg(text, streaming=False, metadata=metadata)
            except Exception as e:
                st.error(str(e))
                chat_box.update_msg(f"抱歉，处理请求时出现错误：{str(e)}", streaming=False)
