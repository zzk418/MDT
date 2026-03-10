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
            "title": "转移性激素敏感性前列腺癌",
            "description": "男性68岁，排尿困难3个月，腰背部疼痛1个月，PSA 85 ng/mL，骨扫描多发骨转移",
            "difficulty": "高级",
            "tags": ["转移性", "内分泌治疗", "骨转移", "MDT"],
            "content": """
## 基本信息
- 患者：男性，68岁，退休工人
- 主诉：排尿困难3个月，腰背部疼痛1个月加重
- 既往史：高血压10年（氨氯地平5mg/日控制良好），否认其他重大疾病
- 家族史：兄长有前列腺癌病史

## 体格检查
- ECOG评分：1分
- 直肠指检（DRE）：前列腺III度增大，质硬，表面结节感，中央沟消失
- 腰椎L3-L4压痛（+）

## 实验室检查
- PSA：85.3 ng/mL（正常 <4.0）
- 游离PSA/总PSA：0.08
- 血常规：Hb 102 g/L（轻度贫血）
- 肝肾功能：正常
- 碱性磷酸酶（ALP）：285 U/L（↑，正常 <150）

## 影像学检查
- mpMRI（多参数MRI）：前列腺外周带双侧T2低信号结节，PI-RADS 5分；包膜外侵犯（EPE），精囊受侵（SVI）；盆腔多发淋巴结肿大，最大1.8cm
- 全身骨扫描：脊柱（T10、L2、L3、L4）、骨盆、双侧肋骨多发放射性浓聚（多发骨转移）
- PSMA PET-CT：前列腺原发灶高摄取，多发骨转移，盆腔及腹膜后淋巴结转移

## 病理结果
- 系统性12针穿刺活检：阳性8针/12针
- Gleason评分：4+5=9分（ISUP 5级）
- 侵犯神经周围

## 临床分期
- TNM分期：T3bN1M1b（骨转移）
- 危险分层：转移性激素敏感性前列腺癌（mHSPC），高瘤负荷

## MDT参与科室及讨论要点

### 泌尿外科
- 是否需要原发灶减瘤手术（减瘤性前列腺切除术）？
- 高瘤负荷 mHSPC 的局部治疗价值（STAMPEDE 试验数据）
- 骨转移椎体稳定性评估，脊髓压迫风险

### 肿瘤内科
- 雄激素剥夺治疗（ADT）基础方案：LHRH激动剂 vs 拮抗剂
- 联合强化方案选择：ADT + 多西他赛 vs ADT + 新型内分泌药（阿比特龙/恩扎鲁胺/阿帕他胺）
- STAMPEDE、CHAARTED、LATITUDE试验结论应用
- 治疗毒性管理（骨质疏松、心血管风险）

### 放疗科
- 低瘤负荷患者原发灶放疗获益（STAMPEDE试验）
- 本例高瘤负荷是否有原发灶放疗指征？
- 症状性骨转移姑息放疗：单次8Gy vs 多次分割
- 脊柱转移灶立体定向放疗（SBRT）可能性

### 骨科/疼痛科
- L3-L4骨转移椎体稳定性评估（SINS评分）
- 双膦酸盐（唑来膦酸）vs RANK-L抑制剂（地舒单抗）骨保护治疗
- 疼痛管理：三阶梯止痛方案

### 病理科
- BRCA1/2、ATM 等同源重组修复（HRR）基因检测建议
- MSI/MMR状态检测（免疫治疗适应证）

### 影像科
- PSMA PET-CT 对分期的价值超越传统骨扫描+CT
- 治疗响应评估：PSA动力学 + 影像随访频率

## NCCN/EAU指南推荐（2024）
- 高瘤负荷 mHSPC 首选：ADT + 多西他赛（6周期）或 ADT + 阿比特龙+泼尼松 或 ADT + 阿帕他胺
- 骨保护：推荐使用地舒单抗或唑来膦酸
- 补充维生素D和钙剂预防骨质疏松

## 讨论结论
- 诊断：转移性激素敏感性前列腺癌（mHSPC），高瘤负荷，Gleason 9分
- 推荐方案：ADT（LHRH拮抗剂地加瑞克）+ 阿比特龙1000mg/日+泼尼松5mg bid
- 骨转移：地舒单抗120mg q4w，补充钙剂+VitD
- L3-L4姑息放疗：8Gy/1次
- 随访：每3个月PSA+睾酮，6个月影像评估
"""
        },
        {
            "id": "prostate_002",
            "title": "局限性中危前列腺癌治疗决策",
            "description": "男性63岁，体检PSA 12.5 ng/mL，MRI PI-RADS 4分，穿刺Gleason 3+4=7分，局限于包膜内",
            "difficulty": "中级",
            "tags": ["局限性", "中危", "手术 vs 放疗", "主动监测"],
            "content": """
## 基本信息
- 患者：男性，63岁，工程师，性生活活跃，无排尿症状
- 主诉：常规体检发现PSA升高
- 既往史：2型糖尿病（口服药控制），否认心脑血管疾病
- 家族史：父亲69岁确诊前列腺癌

## 体格检查
- ECOG评分：0分
- DRE：前列腺右侧叶轻度质硬，无明显结节
- 无排尿困难，IPSS评分8分（轻度）

## 实验室检查
- PSA：12.5 ng/mL（1年前PSA 8.2，PSA密度0.18 ng/mL/cm³）
- 游离PSA/总PSA：0.12
- PHI（前列腺健康指数）：55（高风险阈值）

## 影像学
- mpMRI：右侧外周带3点方向结节15mm，T2WI低信号，DWI高信号，PI-RADS 4分；无包膜外侵犯，精囊正常
- 骨扫描：未见骨转移

## 病理（靶向穿刺+系统穿刺，共14针）
- 靶向针2针均阳性：Gleason 3+4=7分（ISUP 2级），癌灶占针长40%
- 系统针：右叶3针阳性，Gleason 3+3=6分（ISUP 1级）
- 左叶：阴性

## 临床分期
- T2bN0M0，中危（D'Amico分级）
- 单侧、包膜内，无不良病理特征

## MDT讨论：三种治疗方案对比

### 方案A：根治性前列腺切除术（RP）
**泌尿外科意见**：
- 机器人辅助腹腔镜（RARP）为首选微创方式
- 优势：明确病理分期，一次性切除，PSA可降至不可测
- 风险：尿失禁（短期30-50%，长期<5%）、勃起功能障碍（神经保留术后1年恢复率60-80%）
- 患者63岁、性功能需求高→神经血管束保留可行性评估

### 方案B：外照射放疗（EBRT）± 近距离放疗
**放疗科意见**：
- IMRT/VMAT技术，总剂量78-80 Gy/39-40次，或SBRT 35-36.25Gy/5次
- 可联合低剂量率（LDR）近距离放疗（粒子植入）提高局控率
- 中危患者可考虑联合短期ADT（4-6个月）
- 优势：无手术风险，勃起功能保留率高
- 风险：放射性直肠炎、膀胱炎（5-10%），继发肿瘤风险（极低）

### 方案C：主动监测（AS）
**泌尿外科/肿瘤内科联合意见**：
- 中危患者AS有争议，ISUP 2级（3+4）的AS数据有限
- ProtecT试验：10年肿瘤特异性生存率在AS/RP/RT三组均>98%
- AS标准：3-6个月PSA复查，12-18个月重复穿刺，MRI每1-2年
- 本例：单侧病灶，PI-RADS 4（非5），可纳入AS讨论

### 病理科补充
- 建议行 Oncotype DX GPS 或 Decipher 基因组检测，辅助风险再分层
- AR-V7检测（若考虑激素治疗）

## 患者意愿与个体化因素
- 患者关注性功能保留 → 倾向放疗或神经保留手术
- 糖尿病 → 手术及放疗均可，愈合略慢
- 活跃工作状态 → 偏向一次性根治方案

## 循证依据
- ProtecT试验（2016/2023更新）：15年随访三组无明显总生存差异
- NCCN 2024：中危患者RP/EBRT/AS均为可选，个体化决策

## MDT推荐
首选：RARP（神经保留），术前基因组检测辅助决策；次选：SBRT 5次分割方案（PACE-B试验支持）
"""
        },
        {
            "id": "prostate_003",
            "title": "去势抵抗性前列腺癌（CRPC）的后线治疗",
            "description": "男性71岁，前列腺癌根治术后ADT治疗3年，PSA持续升高至45 ng/mL，骨转移进展",
            "difficulty": "高级",
            "tags": ["CRPC", "去势抵抗", "后线治疗", "PARP抑制剂"],
            "content": """
## 基本信息
- 患者：男性，71岁
- 病史：2021年行RARP（pT3aN0M0，Gleason 4+4=8）
- 术后PSA未降至不可测（术后3个月PSA 0.8），提示生化复发
- 2022年起ADT治疗（LHRH激动剂）+多西他赛6周期，PSA一度降至3.2
- 2024年PSA再次升高至45 ng/mL，睾酮 <50 ng/dL（确认去势状态）

## 当前状态（CRPC诊断）
- PSA：45.2 ng/mL（3个月内连续3次升高）
- 睾酮：18 ng/dL（去势水平）
- 影像：PSMA PET-CT示多发骨转移进展（新增肋骨、股骨病灶），无内脏转移
- ECOG：1分，NRS疼痛评分3分（骨痛）

## 基因检测结果
- BRCA2胚系突变（致病性）
- MSS（微卫星稳定），TMB低

## MDT讨论：CRPC后线治疗选择

### 肿瘤内科
**一线后续方案（既往多西他赛后）**：
1. **奥拉帕利（PARP抑制剂）**：BRCA2突变患者首选
   - PROfound试验：BRCA1/2突变mCRPC，奥拉帕利vs恩扎鲁胺/阿比特龙，rPFS 7.4 vs 3.6月，OS获益
   - 用法：奥拉帕利300mg bid，口服
   - 主要副作用：贫血、恶心、疲劳，BRCA2突变需监测血液毒性
2. **卡巴他赛（紫杉类后线）**：多西他赛失败后可选
3. **镭-223（Xofigo）**：有症状骨转移，无内脏转移
   - ALSYMPCA试验：改善OS 3.6个月，降低骨相关事件
   - 本例适合（骨转移为主，ECOG良好）

### 泌尿外科
- 评估是否有局部症状（尿路梗阻等）需外科干预

### 放疗科
- PSMA靶向放射配体治疗（PSMA-RLT，Lu-177-PSMA-617）
  - VISION试验：mCRPC中位rPFS 8.7月（vs 3.4月），OS延长4个月
  - 需PSMA PET阳性（本例满足）
  - 与奥拉帕利联合探索性研究进行中（TheraP-COMBO）

### 骨科/姑息科
- 地舒单抗持续使用（已用）
- 股骨转移灶：评估骨折风险（Mirels评分），必要时预防性内固定
- 疼痛：羟考酮缓释片 + 骨转移处放疗

### 基因/精准医学
- BRCA2胚系突变→建议家属（一级亲属）遗传咨询和检测
- HRR通路其他基因（CDK12等）状态

## 推荐方案
**首选**：奥拉帕利300mg bid（BRCA2突变，获益最大）
**联合**：镭-223 q4w×6周期（症状性骨转移，与奥拉帕利需注意联合血液毒性）
**支持治疗**：地舒单抗 + 羟考酮 + 症状性骨转移姑息放疗
**随访**：每8周PSA+影像，监测血常规、肝功
"""
        }
    ],
    "膀胱癌": [
        {
            "id": "bladder_001",
            "title": "肌层浸润性膀胱癌新辅助化疗与根治术",
            "description": "男性68岁，无痛性肉眼血尿2个月，TURBT证实高级别肌层浸润性膀胱癌（T2），无远处转移",
            "difficulty": "高级",
            "tags": ["MIBC", "新辅助化疗", "根治性膀胱切除", "尿流改道"],
            "content": """
## 基本信息
- 患者：男性，68岁，吸烟史40年（20支/天，已戒烟5年）
- 主诉：无痛性肉眼血尿2个月，1次血块
- 既往史：高血压，冠心病（PCI术后4年，服阿司匹林+他汀），肾功能正常（eGFR 72 mL/min）
- 职业史：接触芳香胺（印染工人20年）

## 体格检查
- ECOG 1分，无淋巴结肿大，腹部无包块

## 检查结果
- 膀胱镜：膀胱左侧壁3×3cm菜花样肿瘤，基底宽，无蒂，周围黏膜充血
- CTU：膀胱左侧壁增厚约1.5cm，膀胱外脂肪清晰，无远处淋巴结及转移
- 胸部CT：无转移
- TURBT病理：高级别尿路上皮癌，浸润固有肌层（muscularis propria）→ T2期
- 再次TURBT（re-TURBT）：残余肌层浸润，Pd-L1表达10%（CPS）

## 分期
- cT2N0M0，肌层浸润性膀胱癌（MIBC）

## MDT讨论要点

### 泌尿外科
**根治性膀胱切除术（RC）方案**：
- 标准术式：根治性膀胱切除+盆腔淋巴结清扫（PLND）
- 男性：切除膀胱+前列腺+精囊；女性：切除膀胱+子宫+卵巢（本例男性）
- 微创方式：机器人辅助腹腔镜（RARC）与开放比较：出血少，恢复快，肿瘤结局相当
- 尿流改道方式讨论：
  1. 回肠输出道（Bricker术）：简单可靠，需造口护理
  2. 正位新膀胱（Studer术）：保留排尿功能，需条件（尿道切缘阴性、肾功能足够）
  3. 可控性皮肤造口：本例患者倾向保留生活质量 → 新膀胱为首选
- 冠心病PCI史：麻醉科需评估停用阿司匹林风险

### 肿瘤内科
**新辅助化疗（NAC）指征**：
- 证据：SWOG 8710试验，NAC（MVAC方案）后RC vs单独RC，5年OS 57% vs 43%
- 推荐：顺铂适合患者（eGFR≥60，ECOG≤2，心功能正常）首选GC或剂量密集型MVAC
- 本例eGFR 72，冠心病稳定 → 可用顺铂
- 方案：GC（吉西他滨+顺铂），3-4周期后再评估
- NAC后病理降期（≤pT1或pCR）提示预后改善

### 放疗科
**膀胱保留三联方案（TMT）**：
- 适应证：单发病灶、T2-T3a、无原位癌、肾积水（本例部分符合）
- 方案：最大化TURBT + 同步放化疗（顺铂+放疗）
- TMT 5年OS 50-60%，肌层浸润性复发率10-15%
- 本例患者有生育意愿（已无）但希望保留自然排尿 → TMT为可选方案

### 病理科
- 建议FGFR3突变检测（用于后续厄达菲替尼靶向治疗）
- HER2状态（曲妥珠单抗+化疗研究进行中）
- Pd-L1表达10%（CPS）→ 后续辅助免疫治疗参考

### 肿瘤内科（辅助治疗）
- 根治术后pT3/pT4或N+患者：辅助nivolumab（CheckMate 274试验）改善DFS
- 本例若术后病理升期（pT3以上）→ 推荐nivolumab辅助1年

## MDT推荐方案
1. NAC：GC方案3周期（吉西他滨1250mg/m² D1、D8 + 顺铂70mg/m² D1，每21天）
2. NAC后影像评估：若有效（缩小≥30%或降期），继续RC
3. RC：RARC + 扩大PLND + 正位新膀胱（Studer回肠新膀胱）
4. 术后：若pT3/N+，nivolumab辅助治疗（240mg q2w，共1年）
5. 随访：术后3个月膀胱镜+影像，新膀胱功能评估
"""
        },
        {
            "id": "bladder_002",
            "title": "高危非肌层浸润性膀胱癌（NMIBC）的BCG治疗",
            "description": "男性55岁，反复膀胱肿瘤，TUR后高级别T1+原位癌，需评估BCG治疗和根治手术时机",
            "difficulty": "中级",
            "tags": ["NMIBC", "高危", "BCG", "原位癌"],
            "content": """
## 基本信息
- 患者：男性，55岁
- 病史：2年前首次TUR膀胱肿瘤（T1G3），术后BCG灌注维持18个月
- 复发：末次随访膀胱镜发现新病灶，活检高级别T1+广泛CIS（原位癌）

## 检查结果
- 膀胱镜：膀胱颈部2cm绒毛状肿瘤 + 多处扁平红色区域（CIS）
- TUR病理：高级别尿路上皮癌T1，肌层未见肿瘤；广泛CIS（多点活检阳性）
- 脂肪层未侵犯，淋巴管浸润（LVI）（+）
- CTU：上尿路无异常，无淋巴结肿大

## 危险分层
- EORTC高危 + BCG失败（BCG-unresponsive）
- 高危因素：T1G3 + CIS + 复发 + LVI

## MDT讨论

### 泌尿外科
**BCG无效的处理**：
- BCG-unresponsive定义：充分BCG后（至少5/6诱导+2/3维持）3个月内复发高级别病变
- 强烈推荐根治性膀胱切除（RC）：延迟RC导致进展风险显著增加（1年进展率30-40%）
- 患者55岁，较年轻，RC后正位新膀胱预后好

**保膀胱选项（若患者拒绝RC）**：
- 纳武利尤单抗（PD-1抑制剂）：FDA获批用于BCG无效高危NMIBC
- Pembrolizumab：KEYNOTE-057，3个月CRR 41%，12个月持续CR 19%
- 膀胱内吉西他滨+多西他赛联合灌注

### 肿瘤内科
- 若接受保膀胱：pembrolizumab 200mg q3w×2年，同时严密监测进展
- 进展至T2后立即RC

### 放疗科
- T1 NMIBC不常规放疗；若不适合手术，可考虑TMT

## 推荐
首选：根治性膀胱切除（鉴于BCG无效、高危、患者年轻）
次选：pembrolizumab膀胱内灌注（若强烈拒绝手术，需严密监测）
"""
        }
    ],
    "肾癌": [
        {
            "id": "kidney_001",
            "title": "局限性肾细胞癌保留肾单位手术决策",
            "description": "男性48岁，体检发现右肾4.5cm肿瘤，R.E.N.A.L评分10分，对侧肾功能正常，希望保留肾功能",
            "difficulty": "高级",
            "tags": ["肾细胞癌", "保留肾单位", "机器人手术", "消融"],
            "content": """
## 基本信息
- 患者：男性，48岁，糖尿病10年（血糖控制欠佳）
- 主诉：体检腹部超声发现右肾占位
- 既往史：2型糖尿病，高血压，双肾微量蛋白尿（早期糖尿病肾病）
- 家族史：母亲患肾癌

## 检查结果
- 增强CT：右肾中极4.5cm实性占位，增强明显强化（动脉期150HU，静脉期75HU），边界欠清，与集合系统关系密切
- R.E.N.A.L评分：10分（高复杂性）
- 对侧肾：左肾正常，eGFR 58 mL/min（轻中度慢性肾病）
- 核医学分肾功能：右肾45%，左肾55%
- 穿刺活检（术前可选）：透明细胞肾细胞癌，Fuhrman 3级

## 分期
- cT2aN0M0，局限性肾细胞癌

## MDT讨论：手术方案选择

### 泌尿外科
**方案比较**：

| | 机器人辅助肾部分切除（RAPN）| 开放肾部分切除（OPN）| 根治性肾切除（RN）|
|---|---|---|---|
| 适应证 | 复杂性肿瘤，技术条件好 | 高复杂性，R.E.N.A.L≥10 | 肿瘤过大或位置不利 |
| 热缺血时间 | 目标<25分钟 | 经验术者<20分钟 | 无缺血 |
| 肾功能保留 | 优 | 最优 | 损失对侧肾功能代偿 |
| 切缘阳性率 | ~5% | ~3% | 不适用 |

**本例**：
- R.E.N.A.L 10分（高复杂性）→ 首选开放或机器人辅助，技术要求高
- 糖尿病肾病+eGFR 58，保留肾单位极为重要
- 有丰富机器人辅助经验的中心：RAPN可行，需控制热缺血时间<20分钟
- 术中超声引导 + 3D重建规划手术切面

**消融治疗（射频/冷冻消融）**：
- 适应证：≤3cm、不适合手术的患者
- 本例4.5cm、R.E.N.A.L高复杂 → 消融不是首选，局控率不如手术
- 糖尿病史 → 消融后愈合问题，复发率相对高

### 血管外科/介入科
- 术前超选择性肾动脉栓塞：可减少术中出血，但争议较大
- 本例集合系统紧邻 → 术中注意集合系统修补

### 内分泌科（糖尿病管理）
- 围手术期血糖控制目标：8-10 mmol/L
- 停用SGLT-2抑制剂（若在用），术前3天改用胰岛素
- 术后肾功能监测：RCC根治后残余肾功能保护

### 肿瘤内科（术后随访）
- 局限性RCC术后：标准随访（无辅助靶向治疗证据，ASSURE/PROTECT试验均为阴性）
- pT2高危（Fuhrman 4级、肿瘤坏死等）：舒尼替尼辅助尚无定论
- 随访：3-6个月CT，持续5年

### 遗传/基因
- 母亲患肾癌 → 考虑遗传性肾癌综合征（VHL、HLRCC、SDH突变）
- 推荐：VHL/FLCN/MET/FH基因检测，如有突变家属应接受筛查

## MDT推荐
- 手术：机器人辅助肾部分切除术（RAPN），3D重建规划，目标热缺血<20分钟
- 术前：遗传基因检测，内分泌科优化血糖管理
- 术后：每3个月随访eGFR，6个月胸腹CT复查
"""
        },
        {
            "id": "kidney_002",
            "title": "转移性肾细胞癌靶向免疫联合治疗",
            "description": "男性56岁，肾癌根治术后3年，发现双肺及肝多发转移，IMDC中危，评估一线靶向免疫方案",
            "difficulty": "高级",
            "tags": ["转移性肾癌", "靶向治疗", "免疫治疗", "IMDC"],
            "content": """
## 基本信息
- 患者：男性，56岁
- 病史：2021年右肾根治切除（pT3aN0，透明细胞癌，Fuhrman 4级）
- 术后18个月常规随访发现：双肺多发结节（最大2.1cm），肝脏2个病灶（1.5cm、2.3cm）
- 穿刺病理：肾透明细胞癌转移，Pd-L1 TPS 20%

## 当前状态
- ECOG 1分
- IMDC评分：2分（中危，时间<1年不符合，血红蛋白偏低）
- 实验室：Hb 105 g/L，LDH正常，钙正常，中性粒细胞正常
- 靶器官：肺（可测量）+ 肝（可测量），无骨转移，无脑转移

## MDT讨论：一线治疗方案

### 肿瘤内科
**循证医学证据（2024年）**：

| 方案 | 试验 | ORR | mPFS | mOS |
|------|------|-----|------|-----|
| 纳武利尤单抗+卡博替尼 | CheckMate 9ER | 56% | 16.6m | 37.7m |
| 帕博利珠单抗+阿昔替尼 | KEYNOTE-426 | 60% | 15.4m | 45.7m |
| 纳武利尤单抗+伊匹木单抗 | CheckMate 214 | 39% | 11.6m | 47m（中危） |
| 舒尼替尼（单药TKI）| 历史对照 | 31% | 8-9m | 26-30m |

**本例推荐（中危，Pd-L1 20%）**：
- 首选：帕博利珠单抗200mg q3w + 阿昔替尼5mg bid（KEYNOTE-426）
- 替选：纳武利尤单抗+卡博替尼（骨转移/高血管生成特征时略优）
- 免疫+免疫（纳武+伊匹）：中危OS最优，但毒性管理复杂，PD-L1低时不占优势

**毒性管理**：
- 免疫相关不良事件（irAE）：甲状腺功能异常（30%），肺炎（5%），肝炎（5%）
- TKI相关：高血压（40%），手足综合征（30%），腹泻
- 联合用药需心脏科、内分泌科、消化科备用会诊

### 泌尿外科
- 转移性RCC：减瘤性肾切除（CN）价值下降（CARMENA试验）
- 中危患者：IMDC评分2-3分，延迟CN（先系统治疗，转化后再评估）
- 本例已行根治切除（术后转移），无减瘤手术指征

### 放疗科
- 寡转移灶SBRT（<5个病灶）：增加局控，延迟系统治疗时间
- 本例多发肺肝转移，不符合寡转移定义
- 若出现骨/脑转移：放疗重要

### 介入科
- 肝脏病灶：肝动脉化疗栓塞（TACE）或射频消融（RFA）辅助系统治疗可探索

### 心理科/营养科
- 免疫联合靶向治疗周期长（2年+），心理支持和营养管理重要

## MDT推荐
**一线方案**：帕博利珠单抗200mg q3w + 阿昔替尼5mg bid，持续至疾病进展或毒性不耐受
**基线评估**：甲功、心肌酶、肝功、尿蛋白、血压
**随访**：每8周影像评估（mRECIST），毒性监测每2周
"""
        }
    ],
    "尿路上皮癌（上尿路）": [
        {
            "id": "utuc_001",
            "title": "高级别上尿路尿路上皮癌（UTUC）的手术与辅助治疗",
            "description": "女性62岁，左输尿管中段高级别尿路上皮癌，肾积水，评估根治手术与保肾方案",
            "difficulty": "中级",
            "tags": ["上尿路", "输尿管癌", "肾输尿管切除", "保肾"],
            "content": """
## 基本信息
- 患者：女性，62岁
- 主诉：左腰部隐痛1个月，偶有肉眼血尿
- 既往史：Lynch综合征家族史（哥哥结肠癌，母亲子宫内膜癌）

## 检查结果
- CTU：左输尿管中段充盈缺损15mm，近端肾盂积水（中度）
- 输尿管镜：左输尿管中段乳头状肿瘤，活检高级别尿路上皮癌
- 尿细胞学：阳性
- 胸腹CT：无远处转移，左侧盆腔一枚可疑淋巴结7mm
- 对侧：右肾功能正常，eGFR 65 mL/min（双侧）

## 分期
- cT2N?M0，高级别UTUC

## MDT讨论

### 泌尿外科
**根治性肾输尿管切除+膀胱袖状切除（RNU）**：
- 金标准：腹腔镜/机器人辅助RNU
- 范围：左肾+全段输尿管+膀胱袖（含输尿管口）
- 淋巴结清扫：中段输尿管→清扫主动脉旁、髂总淋巴结

**保肾方案（输尿管镜消融）**：
- 适应证：低级别、孤立肾、双侧病变、肾功能不全
- 本例高级别→保肾局控率低，强烈推荐RNU

### 肿瘤内科
**新辅助化疗**：
- 理由：RNU后肾功能下降（eGFR降至40-50），无法给予顺铂辅助化疗
- POUT试验：辅助吉西他滨+顺铂→DFS显著改善（HR 0.49）
- 建议：术前给予GC方案1-2周期（窗口期化疗），评估疗效后RNU

**辅助免疫治疗**：
- 帕博利珠单抗辅助：JAVELIN Upper 01正在进行（UTUC辅助免疫）
- Lynch综合征患者MSI-H比例高（>80%）→强力支持免疫治疗应用

### 遗传/基因
- Lynch综合征相关UTUC：MLH1/MSH2/MSH6/PMS2检测
- 本例强烈建议胚系MMR基因检测
- Lynch综合征患者：终生高危（结肠癌、子宫内膜癌、卵巢癌）→多学科筛查

### 妇科
- Lynch综合征合并UTUC的女性：子宫内膜癌风险40-60%，卵巢癌风险10-12%
- 讨论：是否同期预防性子宫+双附件切除（患者绝经后）

## MDT推荐
1. 新辅助GC化疗1周期（评估反应）
2. 机器人辅助RNU + 盆腔淋巴结清扫
3. 术后病理：若pT3+或N+→辅助免疫（帕博利珠单抗/nivolumab）
4. 遗传咨询 + Lynch综合征管理
5. 定期膀胱镜随访（膀胱复发率30%）
"""
        }
    ],
    "肾上腺肿瘤": [
        {
            "id": "adrenal_001",
            "title": "肾上腺意外瘤的鉴别诊断与处理",
            "description": "女性52岁，因腰痛CT偶然发现右肾上腺3.5cm肿瘤，激素水平轻度异常，需鉴别功能性与恶性",
            "difficulty": "中级",
            "tags": ["肾上腺意外瘤", "嗜铬细胞瘤", "皮质醇腺瘤", "腹腔镜"],
            "content": """
## 基本信息
- 患者：女性，52岁
- 主诉：右腰部不适，CT发现右肾上腺占位（偶然发现，incidentaloma）
- 既往史：高血压5年（药物控制欠佳，阵发性加重），体重增加，满月脸

## 检查结果
- 增强CT：右肾上腺3.5cm类圆形肿块，平扫CT值12HU，增强后60HU，廓清率>60%（腺瘤特征）
- 24h尿儿茶酚胺/甲氧基肾上腺素（MN）：升高3倍（嗜铬细胞瘤可疑）
- 血浆游离MN：升高
- 皮质醇昼夜节律：消失，1mg地塞米松抑制试验：不被抑制（≥1.8 μg/dL）→亚临床库欣综合征
- 醛固酮/肾素比（ARR）：正常
- DHEAS：偏低

## 初步判断
- 功能性肾上腺腺瘤（双重功能：嗜铬细胞瘤？+ 亚临床皮质醇增多症？）
- 首先排除嗜铬细胞瘤（手术高风险）

## MDT讨论

### 泌尿外科/内分泌外科
**手术指征**：
- 功能性肿瘤（任何大小）均需手术
- 无功能腺瘤：>4cm 或 随访增大
- 本例3.5cm + 疑似功能性 → 手术指征明确

**术前准备（嗜铬细胞瘤）**：
- 酚苄明（α阻断剂）术前10-14天，充分α阻断
- 补充容量（扩容）
- 心率>100 → 加β阻断剂（必须在α阻断后）
- 禁用β阻断剂单独使用（危险）

**手术方式**：腹腔镜肾上腺切除术（优先后腹腔镜）

### 内分泌科
- 嗜铬细胞瘤确认：血/尿MN最敏感（97%灵敏度）
- 亚临床库欣：ACTH低，皮质醇升高，骨密度检查（骨质疏松）
- 双重功能？：嗜铬细胞瘤伴随皮质醇分泌（少见，约5%）
- 术后：肾上腺皮质功能不足风险（需氢化可的松替代治疗）

### 麻醉科
- 嗜铬细胞瘤手术高危：术中血压波动（高达300mmHg）、心律失常、急性心衰
- 需经验丰富的麻醉团队，备硝普钠、酚妥拉明
- 术中动脉置管（有创血压）

### 影像科
- MIBG（间碘苄胍）显像：确认嗜铬细胞瘤（本例不强制，MN升高已高度可疑）
- PET-CT（68Ga-DOTATATE）：多发病灶或恶性嗜铬细胞瘤排查
- 双侧肾上腺评估：排除双侧病变（MEN2）

## MDT推荐
1. 确认充分α阻断（酚苄明14天，血压<130/80，立位心率90-100）
2. 腹腔镜后腹腔镜肾上腺切除术
3. 术后激素替代：氢化可的松20mg（早）+10mg（下午）
4. 术后随访：6周血浆MN复查，骨密度，皮质醇轴恢复评估
5. 遗传检测：排除MEN2（RET）、VHL、SDHB（恶性嗜铬细胞瘤相关）
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
    base_prompt = """你是一位经验丰富的泌尿外科专家和医学教育者，专门从事AI+MDT诊疗教学。请根据当前教学模式提供专业、准确的医学指导。请始终使用中文回答，不得使用英文作答。"""
    
    if teaching_mode == "案例分析":
        if selected_case:
            case_info = f"""
## 当前教学案例

**案例标题**：{selected_case['title']}
**案例难度**：{selected_case['difficulty']}
**标签**：{', '.join(selected_case.get('tags', []))}

### 完整病例资料

{selected_case.get('content', selected_case.get('description', ''))}
"""
        else:
            case_info = "尚未选择教学案例，请指导学员从侧边栏选择案例。"

        return base_prompt + f"""
你正在指导住院医师进行 MDT 案例分析教学。你已获得以下完整病例资料，请基于这些真实数据进行教学。

{case_info}

**教学原则**：
1. 基于上述病例真实数据进行分析，不要凭空编造或偏离病例内容
2. 鼓励学员独立思考，通过提问引导而非直接给出答案
3. 提供循证医学依据，引用 NCCN、EAU、中国泌尿外科指南等权威来源
4. 强调 MDT 多学科协作的必要性和各学科职责
5. 指出常见诊断和治疗误区，培养批判性临床思维

用专业、友好的语气交流。回答时请明确基于病例中的具体数据（如 PSA 值、影像结果、病理分期等）。
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
        default_kb = Settings.kb_settings.DEFAULT_KNOWLEDGE_BASE
        kb_index = kb_list.index(default_kb) if default_kb in kb_list else 0
        selected_kb = st.selectbox(
            "关联知识库",
            kb_list,
            index=kb_index,
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
            chat_endpoint = f"{api_url}/knowledge_base/local_kb/{selected_kb}/chat/completions"
            chat_box.ai_say([
                Markdown("...", in_expander=True, title=f"知识库「{selected_kb}」匹配结果", state="running"),
                f"正在查询知识库 `{selected_kb}`，请稍候...",
            ])
            payload = dict(
                messages=messages,
                model=ctx.get("llm_model"),
                stream=True,
                top_k=kb_top_k,
                score_threshold=score_threshold,
                temperature=ctx.get("temperature"),
                prompt_name="default",
                return_direct=False,
            )
            text = ""
            first = True
            try:
                with httpx.Client(timeout=httpx.Timeout(300.0, connect=10.0)) as hclient:
                    with hclient.stream("POST", chat_endpoint, json=payload) as resp:
                        resp.raise_for_status()
                        buf = ""
                        for raw in resp.iter_bytes():
                            buf += raw.decode("utf-8", errors="replace")
                            while "\n" in buf:
                                line, buf = buf.split("\n", 1)
                                line = line.strip()
                                if not line or not line.startswith("data:"):
                                    continue
                                data = line[len("data:"):].strip()
                                if data == "[DONE]":
                                    break
                                try:
                                    chunk = json.loads(data)
                                except json.JSONDecodeError:
                                    continue
                                if first:
                                    docs = chunk.get("docs", [])
                                    chat_box.update_msg("\n\n".join(docs), element_index=0, streaming=False, state="complete")
                                    chat_box.update_msg("", element_index=1, streaming=False)
                                    first = False
                                for choice in chunk.get("choices", []):
                                    text += (choice.get("delta") or {}).get("content") or ""
                                if not first:
                                    chat_box.update_msg(text.replace("\n", "\n\n"), element_index=1, streaming=True)
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
