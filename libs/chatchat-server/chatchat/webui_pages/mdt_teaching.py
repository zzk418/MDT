import base64
import hashlib
import io
import json
import os
import re
import uuid
from datetime import datetime
from PIL import Image as PILImage
from typing import Dict, List, Optional
from urllib.parse import urlencode

import httpx
import openai
import streamlit as st
import streamlit_antd_components as sac
from streamlit_chatbox import *
from streamlit_extras.bottom_container import bottom
from streamlit_paste_button import paste_image_button

from chatchat.settings import Settings
from chatchat.server.knowledge_base.model.kb_document_model import DocumentWithVSId
from chatchat.server.knowledge_base.utils import format_reference
from chatchat.server.utils import MsgType, get_config_models, get_config_platforms, get_default_llm, api_address
from chatchat.webui_pages.mdt_kb_lookup import select_context, sources_markdown
from chatchat.webui_pages import mdt_cases
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


TEACHING_MODES = ["案例分析", "虚拟仿真", "团队协作", "考核评估"]


def get_case_studies() -> Dict[str, List[Dict]]:
    """病例优先来自 _cases 目录（改文件即生效，不用重启）；目录为空时回退内置数据。"""
    return mdt_cases.load_cases() or MDT_CASE_STUDIES


def render_case_images(case: Dict) -> None:
    """渲染病例的示教影像；文件不存在就跳过，不影响页面。"""
    images = case.get("images") or []
    if not images:
        return
    cols = st.columns(min(len(images), 2))
    shown = 0
    for i, item in enumerate(images):
        path = mdt_cases.image_abs_path(item.get("path", ""))
        if not path or not path.is_file():
            continue
        with cols[shown % 2]:
            st.image(
                str(path),
                caption=item.get("caption") or path.name,
                use_column_width=True,
            )
        shown += 1
    if shown:
        st.caption("示例影像来自 Wikimedia Commons（PD / CC0 / CC BY），出处见 `_cases/ATTRIBUTION.md`。")


def _find_case(case_id: str) -> Dict:
    for cases in get_case_studies().values():
        for case in cases:
            if case.get("id") == case_id:
                return case
    return {}


def _fill_case_editor(case: Optional[Dict]) -> None:
    """把病例内容灌进编辑器 widget 的 session_state（Streamlit 里 value= 不覆盖已有状态）。"""
    case = case or {}
    st.session_state["mdt_case_id"] = case.get("id", "")
    st.session_state["mdt_case_title"] = case.get("title", "")
    st.session_state["mdt_case_disease"] = case.get("disease", "")
    st.session_state["mdt_case_difficulty"] = case.get("difficulty", "中级")
    st.session_state["mdt_case_tags"] = "，".join(case.get("tags") or [])
    st.session_state["mdt_case_desc"] = case.get("description", "")
    st.session_state["mdt_case_body"] = case.get("content", "")
    st.session_state["mdt_editing_case"] = case.get("id", "")


def render_case_editor() -> None:
    """病例编辑器：新增/修改病例与影像，保存后写文件并同步到私有 git 仓库。"""
    editing_id = st.session_state.get("mdt_editing_case") or ""
    base = _find_case(editing_id) if editing_id else {}
    if editing_id:
        st.info(f"正在编辑：{editing_id}")

    with st.form("mdt_case_form", clear_on_submit=False):
        col1, col2, col3 = st.columns([2, 3, 1])
        col1.text_input("病例 ID（留空自动生成）", key="mdt_case_id")
        col2.text_input("标题", key="mdt_case_title")
        col3.selectbox("难度", ["初级", "中级", "高级"], key="mdt_case_difficulty")
        col4, col5 = st.columns(2)
        col4.text_input("病种", key="mdt_case_disease", help="填已有的归入该病种；填新的会新建分页")
        col5.text_input("标签（逗号分隔）", key="mdt_case_tags")
        st.text_area("一句话摘要", key="mdt_case_desc", height=70)
        st.text_area("病例正文（Markdown）", key="mdt_case_body", height=300)
        uploads = st.file_uploader(
            "添加影像（jpg / png / webp，可多选）",
            type=["jpg", "jpeg", "png", "webp"],
            accept_multiple_files=True,
        )

        existing = base.get("images") or []
        keep: List[Dict] = []
        if existing:
            st.markdown("已有影像（取消勾选即从病例移除，文件仍留在 `_cases/images/`）")
            for i, img in enumerate(existing):
                label = img.get("caption") or img.get("path", "")
                if st.checkbox(label, value=True, key=f"mdt_keep_img_{i}"):
                    keep.append(img)

        submitted = st.form_submit_button("保存病例", type="primary")
        remove = st.form_submit_button("删除该病例")

    if submitted:
        title = (st.session_state.get("mdt_case_title") or "").strip()
        body = (st.session_state.get("mdt_case_body") or "").strip()
        if not title or not body:
            st.error("标题和病例正文不能为空")
            return
        case = {
            "id": (st.session_state.get("mdt_case_id") or "").strip(),
            "title": title,
            "disease": (st.session_state.get("mdt_case_disease") or "").strip() or "未分类",
            "difficulty": st.session_state.get("mdt_case_difficulty") or "中级",
            "tags": [
                t.strip()
                for t in re.split(r"[,，]", st.session_state.get("mdt_case_tags") or "")
                if t.strip()
            ],
            "description": (st.session_state.get("mdt_case_desc") or "").strip(),
            "content": body,
            "images": keep,
        }
        saved = mdt_cases.save_case(case)
        new_images = mdt_cases.save_uploaded_images(saved.stem, list(uploads or []))
        if new_images:
            case["id"] = saved.stem
            case["images"] = keep + new_images
            saved = mdt_cases.save_case(case)
        ok, msg = mdt_cases.sync_to_cloud()
        st.success(f"已保存 `{saved.name}`；{msg}")
        _fill_case_editor(None)
        st.rerun()

    if remove:
        if not editing_id:
            st.warning("先在病例卡片上点「编辑」，再回来删除")
        else:
            mdt_cases.delete_case(editing_id)
            ok, msg = mdt_cases.sync_to_cloud()
            st.success(f"已删除 {editing_id}；{msg}")
            _fill_case_editor(None)
            st.rerun()


def render_case_picker() -> None:
    """进门先选病例：按病种分页的病例卡片墙，外加新增/编辑入口。"""
    studies = get_case_studies()
    total = sum(len(v) for v in studies.values())
    st.subheader("选择教学病例")
    st.caption(
        f"共 {total} 个病例 · {len(studies)} 个病种。病例是 Markdown 文件"
        "（`data/knowledge_base/_cases/`），改文件或在这里新增都立即生效，并同步到私有仓库。"
        "不选病例也可以直接在下方提问。"
    )

    tabs = st.tabs(list(studies.keys()) + ["＋ 新增 / 编辑病例"])
    for tab, (disease, cases) in zip(tabs, studies.items()):
        with tab:
            cols = st.columns(2)
            for i, case in enumerate(cases):
                with cols[i % 2].container(border=True):
                    st.markdown(f"**{case['title']}**")
                    st.caption(f"难度：{case.get('difficulty', '未标注')}")
                    tags = case.get("tags") or []
                    if tags:
                        st.caption("标签：" + "、".join(tags))
                    if case.get("images"):
                        st.caption(f"影像：{len(case['images'])} 张")
                    st.write(case.get("description", ""))

                    col_a, col_b, col_c = st.columns([2, 1, 1])
                    if col_a.button(
                        "开始学习", key=f"mdt_pick_{case['id']}", use_container_width=True
                    ):
                        st.session_state["selected_case"] = case
                        st.session_state["selected_disease"] = disease
                        st.session_state["selected_case_title"] = case["title"]
                        st.rerun()
                    if col_b.button(
                        "编辑", key=f"mdt_edit_{case['id']}", use_container_width=True
                    ):
                        _fill_case_editor(case)
                        st.rerun()
                    armed = st.session_state.get("mdt_del_arm") == case["id"]
                    if col_c.button(
                        "确认删除" if armed else "删除",
                        key=f"mdt_del_{case['id']}",
                        use_container_width=True,
                    ):
                        if not armed:
                            st.session_state["mdt_del_arm"] = case["id"]
                            st.rerun()
                        else:
                            mdt_cases.delete_case(case["id"])
                            _, msg = mdt_cases.sync_to_cloud()
                            st.session_state["mdt_del_arm"] = ""
                            st.toast(f"已删除 {case['id']}；{msg}")
                            st.rerun()
    with tabs[-1]:
        render_case_editor()


def render_case_header(selected_case: dict, teaching_mode: str) -> None:
    """顶部状态条：当前病种/病例/环节 + 换病例。"""
    left, right = st.columns([5, 1])
    with left:
        st.markdown(f"**当前病例：{selected_case['title']}**")
        st.caption(
            f"{st.session_state.get('selected_disease', '')}｜"
            f"难度：{selected_case.get('difficulty', '未标注')}｜"
            f"当前环节：{teaching_mode}"
        )
    with right:
        if st.button("换病例", use_container_width=True, key="mdt_change_case"):
            st.session_state["selected_case"] = None
            st.rerun()
    st.divider()


def render_mode_steps() -> str:
    """四步学习路径条：当前位置高亮，可点击切换。返回当前模式。"""
    current = st.session_state.get("teaching_mode", TEACHING_MODES[0])
    if current not in TEACHING_MODES:
        current = TEACHING_MODES[0]

    cols = st.columns(len(TEACHING_MODES))
    for i, mode in enumerate(TEACHING_MODES):
        active = mode == current
        if cols[i].button(
            f"{i + 1}. {mode}",
            use_container_width=True,
            type="primary" if active else "secondary",
            key=f"mdt_mode_step_{i}",
        ) and not active:
            st.session_state["teaching_mode"] = mode
            st.rerun()

    st.progress(
        (TEACHING_MODES.index(current) + 1) / len(TEACHING_MODES),
        text=f"学习路径：第 {TEACHING_MODES.index(current) + 1} / {len(TEACHING_MODES)} 步 · {current}",
    )
    return current


def init_mdt_widgets():
    """初始化MDT教学组件"""
    st.session_state.setdefault("selected_disease", "前列腺癌")
    st.session_state.setdefault("selected_case", None)
    st.session_state.setdefault("teaching_mode", "案例分析")
    st.session_state.setdefault("assessment_scores", {})
    st.session_state.setdefault("discussion_records", [])
    st.session_state.setdefault("mdt_selected_kb", Settings.kb_settings.DEFAULT_KNOWLEDGE_BASE)
    st.session_state.setdefault("cur_conv_name", chat_box.cur_chat_name)
    st.session_state.setdefault("last_conv_name", chat_box.cur_chat_name)


def build_teaching_system_prompt(teaching_mode: str, selected_case: dict = None) -> str:
    """构建教学专用的系统提示词"""
    base_prompt = """你是一位经验丰富的泌尿外科专家和医学教育者，专门从事AI+MDT诊疗教学。请根据当前教学模式提供专业、准确的医学指导。"""
    
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
            case_info = "尚未选择教学病例，请先在病例列表中选择一个病例。"

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


def _submit_for_review(task: str, answer: str, rubric: str, mode_label: str) -> bool:
    """把学生作答交给模型按评分点点评（先答后评）。

    返回是否已提交。所有模式共用这一条出口：先让学生给出判断，再让模型对照
    病例与知识库逐条点评，而不是直接抛一篇标准答案。
    """
    if not (answer or "").strip():
        st.warning("先写下你的判断再提交，这样才能给出有针对性的点评。")
        return False

    case = st.session_state.get("selected_case") or {}
    st.session_state["pending_prompt"] = (
        f"【{mode_label} · 先答后评】\n"
        f"当前病例：{case.get('title', '未选择')}\n"
        f"任务：{task}\n\n"
        f"我的作答：\n{answer.strip()}\n\n"
        "请按下面顺序点评，不要直接重写一整篇标准答案：\n"
        "1. 先指出我答对的部分，逐条对应我的原文；\n"
        "2. 再指出遗漏、含糊或错误的点，说明正确思路；\n"
        f"3. 评分点：{rubric}\n"
        "4. 最后给「参考要点」，并注明依据的知识库文档与章节；\n"
        "5. 如果我的作答与病例资料矛盾，直接指出。"
    )
    return True


def _ask_reference(task: str, mode_label: str) -> None:
    """直接讲参考思路（学生不想先作答时的出口）。"""
    case = st.session_state.get("selected_case") or {}
    st.session_state["pending_prompt"] = (
        f"【{mode_label} · 参考讲解】\n"
        f"当前病例：{case.get('title', '未选择')}\n"
        f"请给出「{task}」的完整参考思路，条理清晰、可直接照着复盘，"
        "并注明依据的知识库文档与章节。"
    )


# ---------------------------------------------------------------------------
# 案例分析：三类任务，先写判断再点评
# ---------------------------------------------------------------------------
CASE_TASKS = [
    {
        "title": "① 诊断与分期",
        "task": "给出诊断、临床分期与危险度分层",
        "question": "请写出：诊断、TNM 分期、分级/风险分层，以及每条判断依据来自病例里的哪项资料。",
        "rubric": "诊断是否准确；分期分级是否正确；是否引用了 PSA/影像/病理等关键依据；是否列出仍需补充的检查",
    },
    {
        "title": "② 治疗决策",
        "task": "给出首选方案、备选方案与理由",
        "question": "请写出：首选治疗方案、备选方案、选择理由，以及需要先补充的资料或前提条件。",
        "rubric": "首选方案是否匹配该分期/风险；是否给出备选方案与切换条件；是否考虑体能状态、合并症与患者意愿；是否说明治疗顺序与随访",
    },
    {
        "title": "③ MDT 协作",
        "task": "给出参与学科、各自要回答的问题与可能分歧",
        "question": "请写出：需要哪些学科参与、每个学科必须回答的关键问题、可能出现的分歧点。",
        "rubric": "学科是否齐全且与病例相关；问题是否具体可回答；是否指出资料缺口与潜在分歧",
    },
]


def display_case_analysis(selected_case):
    """案例分析：病例资料 + 三类任务的先答后评。"""
    if not selected_case:
        st.info("请先在病例列表中选择一个教学病例")
        return

    st.header(f"📊 案例分析：{selected_case['title']}")

    with st.expander("📖 病例详细信息", expanded=True):
        st.markdown(selected_case['content'])

    if selected_case.get("images"):
        with st.expander("🖼️ 影像资料", expanded=True):
            render_case_images(selected_case)

    st.caption("先写自己的判断，再让 AI 按评分点点评——比直接看讲解更接近真实决策训练。")

    tabs = st.tabs([item["title"] for item in CASE_TASKS])
    for tab, item in zip(tabs, CASE_TASKS):
        with tab:
            st.markdown(f"**{item['question']}**")
            answer = st.text_area(
                "我的分析", key=f"mdt_case_ans_{item['title']}", height=160
            )
            col1, col2 = st.columns(2)
            if col1.button(
                "提交点评", key=f"mdt_case_submit_{item['title']}", use_container_width=True
            ):
                if _submit_for_review(item["task"], answer, item["rubric"], "案例分析"):
                    rerun()
            if col2.button(
                "看参考讲解", key=f"mdt_case_ref_{item['title']}", use_container_width=True
            ):
                _ask_reference(item["task"], "案例分析")
                rerun()


# ---------------------------------------------------------------------------
# 虚拟仿真：有步骤的训练，逐步点评
# ---------------------------------------------------------------------------
SIM_SCENARIOS = {
    "影像判读": [
        {
            "title": "选择检查",
            "question": "本病例下一步最该做哪项影像检查？说明它能回答什么问题。",
            "rubric": "检查选择是否与病例阶段匹配；是否说明该检查的目的与预期获得的信息",
        },
        {
            "title": "描述征象",
            "question": "写出你关注的关键影像征象：部位、大小、范围、有无侵犯或转移。",
            "rubric": "描述是否结构化；是否覆盖分期所需的关键信息；是否遗漏重要征象",
        },
        {
            "title": "影像诊断",
            "question": "给出你的影像学诊断与分期判断。",
            "rubric": "结论是否与征象自洽；分期判断是否正确",
        },
        {
            "title": "下一步建议",
            "question": "基于影像结论，写出下一步处理建议及理由。",
            "rubric": "建议是否与分期匹配；是否说明依据与仍需补充的信息",
        },
    ],
    "手术规划": [
        {
            "title": "术前评估",
            "question": "写出术前必须评估的项目与你的结论（分期、体能、器官功能、合并症）。",
            "rubric": "评估项是否完整；是否据此得出可手术/需新辅助等结论",
        },
        {
            "title": "术式选择",
            "question": "写出你选择的手术方式与入路，以及理由。",
            "rubric": "术式是否与分期/肿瘤位置匹配；是否权衡功能保留与手术风险",
        },
        {
            "title": "风险预判",
            "question": "写出术中可能出现的风险与你准备的应对措施。",
            "rubric": "风险是否覆盖出血、邻近器官损伤、淋巴清扫等；应对是否具体可执行",
        },
        {
            "title": "备选方案",
            "question": "如果术中发现无法按计划完成，你的备选方案是什么？",
            "rubric": "备选方案是否现实；是否说明切换条件与术中决策依据",
        },
    ],
    "术后并发症处理": [
        {
            "title": "识别问题",
            "question": "术后第 3 天出现发热与腰痛，写出你的鉴别诊断与首选检查。",
            "rubric": "鉴别诊断是否覆盖感染、尿漏、梗阻等；首选检查是否合理",
        },
        {
            "title": "处理方案",
            "question": "写出你的处理方案（抗感染、引流、支持治疗）与需要观察的指标。",
            "rubric": "处理是否有层次、先救命后治病；观察指标是否具体；是否交代升级条件",
        },
        {
            "title": "多学科协作",
            "question": "这种情况需要哪些学科参与，各自负责什么？",
            "rubric": "学科与职责是否匹配；是否包含上报、家属沟通与随访安排",
        },
    ],
}


def display_virtual_simulation():
    """虚拟仿真：选定场景后按步骤推进，每步先作答再点评。"""
    st.header("🔄 虚拟仿真训练")

    if not st.session_state.get("selected_case"):
        st.info("请先在病例列表中选择一个教学病例")
        return

    current_case = st.session_state.get("selected_case") or {}
    if current_case.get("images"):
        with st.expander("🖼️ 影像资料（作答前先看）", expanded=True):
            render_case_images(current_case)

    scenario = st.selectbox("选择训练场景", list(SIM_SCENARIOS.keys()), key="mdt_sim_scenario")
    steps = SIM_SCENARIOS[scenario]
    step = min(st.session_state.get("mdt_sim_step", 0), len(steps) - 1)
    st.session_state["mdt_sim_step"] = step

    st.progress(
        (step + 1) / len(steps),
        text=f"{scenario}：第 {step + 1} / {len(steps)} 步",
    )

    item = steps[step]
    st.subheader(f"{item['title']}")
    st.markdown(item["question"])

    answer = st.text_area("我的判断", key=f"mdt_sim_ans_{scenario}_{step}", height=140)

    col1, col2, col3 = st.columns(3)
    if col1.button(
        "提交点评", key=f"mdt_sim_submit_{scenario}_{step}", use_container_width=True
    ):
        if _submit_for_review(f"{scenario} · {item['title']}", answer, item["rubric"], "虚拟仿真"):
            records = st.session_state.setdefault("mdt_sim_records", {})
            records[f"{scenario} / {item['title']}"] = answer.strip()
            rerun()
    if col2.button(
        "下一步",
        key=f"mdt_sim_next_{scenario}_{step}",
        use_container_width=True,
        disabled=step >= len(steps) - 1,
    ):
        st.session_state["mdt_sim_step"] = step + 1
        rerun()
    if col3.button("重新开始", key=f"mdt_sim_reset_{scenario}", use_container_width=True):
        st.session_state["mdt_sim_step"] = 0
        rerun()

    records = st.session_state.get("mdt_sim_records") or {}
    if records:
        with st.expander(f"本次已完成的作答（{len(records)} 条）", expanded=False):
            for k, v in records.items():
                st.markdown(f"**{k}**")
                st.caption(v[:200])

    if step == len(steps) - 1 and records:
        if st.button("生成训练复盘", key=f"mdt_sim_summary_{scenario}", use_container_width=True):
            case = st.session_state.get("selected_case") or {}
            detail = "\n\n".join(f"### {k}\n{v}" for k, v in records.items())
            st.session_state["pending_prompt"] = (
                f"【虚拟仿真 · 训练复盘】\n当前病例：{case.get('title', '未选择')}"
                f"\n场景：{scenario}\n\n我在各步骤的作答：\n{detail}\n\n"
                "请生成本次训练复盘：1) 逐步指出我判断正确的关键点；"
                "2) 汇总我反复出现的薄弱环节（按出现次数排序）；"
                "3) 给出 3 条可立刻改进的要点，并注明依据的知识库文档与章节。"
            )
            rerun()


# ---------------------------------------------------------------------------
# 团队协作：三轮讨论，每轮先写发言再点评
# ---------------------------------------------------------------------------
TEAM_ROLES = ["泌尿外科医师", "肿瘤内科医师", "放疗科医师", "病理科医师", "影像科医师", "护理团队"]

TEAM_ROUNDS = [
    {
        "title": "第1轮 · 专科意见",
        "task": "以所选角色给出专科意见",
        "question": "以你选择的角色，写出你对本病例的专科意见：诊断依据、治疗倾向、需要其他学科回答的问题。",
        "rubric": "是否体现本专科视角；意见是否有病例/指南依据；是否提出明确的跨学科问题",
    },
    {
        "title": "第2轮 · 处理分歧",
        "task": "回应其他学科的不同意见并寻求共识",
        "question": "其他学科与你的意见不一致。写出你如何论证自己的观点、如何找到共识。",
        "rubric": "是否正面回应分歧；是否用证据而非立场说话；是否提出可验证的折中方案",
    },
    {
        "title": "第3轮 · 形成结论",
        "task": "作为牵头人形成 MDT 结论",
        "question": "写出你作为本次讨论牵头人形成的 MDT 结论：诊断、首选方案、备选方案、执行分工、随访。",
        "rubric": "结论是否完整可执行；是否包含分工与随访节点；是否吸收了其他学科的意见",
    },
]


def display_team_collaboration():
    """团队协作：学生固定一个角色，分三轮推进，每轮先写发言再点评。"""
    st.header("👥 团队协作")

    if not st.session_state.get("selected_case"):
        st.info("请先在病例列表中选择一个教学病例")
        return

    role = st.selectbox("我扮演的角色", TEAM_ROLES, key="team_role")
    st.caption("AI 扮演其他学科。每轮先写你的发言，再让 AI 从跨学科视角点评。")

    round_idx = min(st.session_state.get("mdt_team_round", 0), len(TEAM_ROUNDS) - 1)
    st.session_state["mdt_team_round"] = round_idx
    item = TEAM_ROUNDS[round_idx]

    st.progress(
        (round_idx + 1) / len(TEAM_ROUNDS),
        text=f"团队协作：第 {round_idx + 1} / {len(TEAM_ROUNDS)} 轮 · {item['title']}",
    )

    st.subheader(item["title"])
    st.markdown(item["question"])

    answer = st.text_area(
        f"我作为{role}的发言", key=f"mdt_team_ans_{round_idx}", height=150
    )

    col1, col2, col3 = st.columns(3)
    if col1.button("提交点评", key=f"mdt_team_submit_{round_idx}", use_container_width=True):
        if _submit_for_review(
            f"{item['task']}（我的角色：{role}）", answer, item["rubric"], "团队协作"
        ):
            rerun()
    if col2.button(
        "让其他学科先发言",
        key=f"mdt_team_others_{round_idx}",
        use_container_width=True,
    ):
        case = st.session_state.get("selected_case") or {}
        st.session_state["pending_prompt"] = (
            f"【团队协作 · 其他学科发言】当前病例：{case.get('title', '未选择')}"
            f"\n我是{role}，当前处于「{item['title']}」。\n"
            "请分别以其他 4 个学科（与我的角色不同）的身份各发表 2-3 句意见，"
            "体现出学科差异与可能的分歧，最后向我提出 2 个必须由我回答的问题。"
        )
        rerun()
    if col3.button(
        "进入下一轮",
        key=f"mdt_team_next_{round_idx}",
        use_container_width=True,
        disabled=round_idx >= len(TEAM_ROUNDS) - 1,
    ):
        st.session_state["mdt_team_round"] = round_idx + 1
        rerun()

    if st.button("汇总我的协作表现", key="mdt_team_summary", use_container_width=True):
        case = st.session_state.get("selected_case") or {}
        st.session_state["pending_prompt"] = (
            f"【团队协作 · 表现汇总】当前病例：{case.get('title', '未选择')}"
            f"\n我的角色：{role}\n\n请从跨学科协作角度评价我的表现："
            "1) 是否站在本专科立场给出了有依据的意见；"
            "2) 是否回应了其他学科的关注点；"
            "3) 形成的结论是否可执行；"
            "4) 给出 2 条最该改进的协作习惯，并注明依据的知识库文档与章节。"
        )
        rerun()


# ---------------------------------------------------------------------------
# 考核评估：四维答题，由模型按权重评分
# ---------------------------------------------------------------------------
ASSESSMENT_QUESTIONS = [
    {
        "dim": "诊断准确性",
        "question": "写出本病例的诊断、分期/风险分层，以及每条判断依据来自哪项资料。",
    },
    {
        "dim": "治疗方案合理性",
        "question": "写出首选治疗方案、备选方案、选择理由，以及切换方案的条件。",
    },
    {
        "dim": "多学科协作",
        "question": "写出需要参与的学科、每个学科要回答的关键问题，以及可能的分歧点。",
    },
    {
        "dim": "沟通表达能力",
        "question": "用患者和家属能听懂的语言，说明本病例的诊疗计划与主要风险（150 字以内）。",
    },
]


def display_assessment_evaluation():
    """考核评估：四道题对应四个维度，提交后由模型按权重评分并给依据。"""
    st.header("📝 学习成果评估")

    selected_case = st.session_state.get("selected_case")
    if not selected_case:
        st.info("请先在病例列表中选择一个教学病例")
        return

    with st.expander("📋 考核病例信息", expanded=False):
        st.markdown(f"**{selected_case['title']}**（难度：{selected_case.get('difficulty', '未标注')}）")
        st.caption(selected_case.get("description", ""))

    st.caption("四道题对应四个考核维度，提交后由模型按权重评分并给出依据；不做自评打分。")

    answers = {}
    tabs = st.tabs([item["dim"] for item in ASSESSMENT_QUESTIONS])
    for tab, item in zip(tabs, ASSESSMENT_QUESTIONS):
        with tab:
            st.markdown(f"**{item['question']}**")
            answers[item["dim"]] = st.text_area(
                "我的作答", key=f"mdt_assess_{item['dim']}", height=150
            )

    if st.button("提交答卷，生成评分", type="primary", key="mdt_assess_submit"):
        empty = [d for d, a in answers.items() if not (a or "").strip()]
        if empty:
            st.warning("还有未作答的维度：" + "、".join(empty))
        else:
            case_title = selected_case["title"]
            weights = "、".join(
                f"{name} {cfg['权重']}" for name, cfg in ASSESSMENT_CRITERIA.items()
            )
            detail = "\n\n".join(
                f"### {item['dim']}\n{answers[item['dim']].strip()}"
                for item in ASSESSMENT_QUESTIONS
            )
            st.session_state["pending_prompt"] = (
                f"【考核评估 · 按维度评分】\n当前病例：{case_title}\n\n"
                f"我的答卷：\n{detail}\n\n"
                f"请按下列维度和权重评分（权重：{weights}）：\n"
                "1. 输出评分表：维度 | 权重 | 得分(0-100) | 判分依据（引用我的原文，并对照病例与知识库）；\n"
                "2. 给出加权总分（0-100）；\n"
                "3. 逐维度指出主要问题与改进方向；\n"
                "4. 给出下一步学习重点。\n"
                "评分必须有依据，不要用「很好/不错」这类空泛评价；"
                "证据要注明依据的知识库文档与章节。"
            )
            rerun()

    st.divider()
    col1, col2 = st.columns(2)
    if col1.button("生成完整考核报告", key="mdt_assess_report", use_container_width=True):
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        detail = "\n\n".join(
            f"### {item['dim']}\n{(answers.get(item['dim']) or '（未作答）').strip()}"
            for item in ASSESSMENT_QUESTIONS
        )
        st.session_state["pending_prompt"] = (
            f"请生成一份完整的 MDT 教学考核评估报告，格式规范、内容专业。\n\n"
            f"考核时间：{now}\n考核病例：{selected_case['title']}"
            f"（难度：{selected_case.get('difficulty', '未标注')}）\n\n"
            f"我的答卷：\n{detail}\n\n"
            "报告应包含：考核概述、各维度详细评价（引用我的原文作为证据）、综合评分分析、"
            "专业发展建议（短期/中期/长期目标），并注明依据的知识库文档与章节。"
        )
        rerun()
    if col2.button("查看评分维度说明", key="mdt_assess_criteria", use_container_width=True):
        st.session_state["pending_prompt"] = (
            "请说明 MDT 教学考核四个维度（诊断准确性 0.3、治疗方案合理性 0.4、"
            "多学科协作 0.2、沟通表达能力 0.1）各自考察什么、评分时看哪些证据，"
            "并给出每个维度「优秀/合格/待改进」的行为描述。"
        )
        rerun()


def mdt_teaching_page(api: ApiRequest, is_lite: bool = False):
    """MDT教学主页面"""
    ctx = chat_box.context
    ctx.setdefault("uid", uuid.uuid4().hex)
    ctx.setdefault("llm_model", get_default_llm())
    ctx.setdefault("temperature", Settings.model_settings.TEMPERATURE)

    # 「高级配置」对话框提交的模型设置在这里落地。
    # 必须放在本页任何 widget 创建之前: Streamlit 规定 widget 实例化之后不能再写
    # 同名 session_state, 否则抛 StreamlitAPIException。
    if st.session_state.pop("_mdt_apply_model_cfg", False):
        for _k in ("platform", "llm_model", "temperature", "system_message"):
            if _k in ctx:
                st.session_state[_k] = ctx[_k]

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
        """模型配置对话框

        注意: 这里必须使用独立的 widget key。侧边栏已经创建了 key="platform" /
        key="llm_model" 的 widget, 而 Streamlit 1.34 的 experimental_dialog 与主页面
        共享 widget key 命名空间, 复用同名 key 会抛 DuplicateWidgetID。
        选完后写入 chat context + 打标记, 由页面顶部的落地逻辑在下一次整页 rerun 时
        应用到 session_state(那时同名 widget 尚未创建, 合法), 从而真正切换模型。
        """
        cols = st.columns(3)
        platforms = ["所有"] + list(get_config_platforms())
        cur_platform = st.session_state.get("platform") or (platforms[0] if platforms else "所有")
        platform = cols[0].selectbox(
            "选择模型平台",
            platforms,
            index=platforms.index(cur_platform) if cur_platform in platforms else 0,
            key="mdt_dlg_platform",
        )
        platform_name_for_api = None if platform == "所有" else platform
        llm_models = list(
            get_config_models(
                model_type="llm", platform_name=platform_name_for_api
            )
        )
        cur_model = st.session_state.get("llm_model", get_default_llm())
        llm_model = cols[1].selectbox(
            "选择LLM模型",
            llm_models,
            index=llm_models.index(cur_model) if cur_model in llm_models else 0,
            key="mdt_dlg_llm_model",
        )
        temperature = cols[2].slider(
            "Temperature",
            0.0,
            1.0,
            value=float(st.session_state.get("temperature", Settings.model_settings.TEMPERATURE)),
            key="mdt_dlg_temperature",
        )
        system_message = st.text_area(
            "System Message:",
            value=st.session_state.get("system_message", ""),
            key="mdt_dlg_system_message",
        )
        if st.button("确定", key="mdt_dlg_ok"):
            ctx["platform"] = platform
            ctx["llm_model"] = llm_model
            ctx["temperature"] = temperature
            ctx["system_message"] = system_message
            # 双保险, 保证"切换模型"一定生效:
            #  ① 对话框是独立 fragment 运行, 主页面那两个同名 widget 不在本次运行中,
            #     直接写 session_state 通常是被允许的 —— 立即生效;
            #  ② 同时打标记, 万一 ① 被 Streamlit 拦截, 由页面顶部的落地逻辑在
            #     下一次整页 rerun 时应用。
            try:
                for _k in ("platform", "llm_model", "temperature", "system_message"):
                    st.session_state[_k] = ctx[_k]
            except Exception as _e:  # noqa: BLE001
                print(f"[mdt] 对话框直写 session_state 未生效, 改由页面顶部落地: {_e}")
            st.session_state["_mdt_apply_model_cfg"] = True
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

    # 侧边栏：只放会话与配置；病例选择在主区（render_case_picker）
    with st.sidebar:
        st.header("🏥 MDT教学系统")

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

        with st.expander("📚 知识库与检索", expanded=False):
            # 知识库关联（API 不可用时退化为仅"不使用知识库", 避免 NoneType 崩溃）
            kb_list = ["不使用知识库"] + [x["kb_name"] for x in (api.list_knowledge_bases() or [])]
            default_kb = Settings.kb_settings.DEFAULT_KNOWLEDGE_BASE
            if default_kb not in kb_list:
                default_kb = "不使用知识库"
            if st.session_state.get("mdt_selected_kb") not in kb_list:
                st.session_state["mdt_selected_kb"] = default_kb
            selected_kb = st.selectbox(
                "关联知识库",
                kb_list,
                key="mdt_selected_kb",
                help="选择知识库后，对话会依据其中的文档回答"
            )
            if selected_kb != "不使用知识库":
                st.selectbox(
                    "资料范围",
                    ["自动匹配病种", "全部文档"],
                    key="mdt_kb_scope",
                    help="显式检索：按提问里的病种/主题关键词选相关文档整篇注入，不依赖向量库与嵌入模型",
                )

            st.divider()

            # 对话轮数配置
            history_len = st.number_input("多轮对话保留轮数", 0, 20, value=5, key="mdt_history_len")

            st.divider()


        with st.expander("🤖 模型配置", expanded=False):
            # 模型配置（内联展示，直接可切换）
            all_platforms = list(get_config_platforms())
            # 默认平台跟随默认模型: 默认模型属于哪个平台就选哪个平台, 都没有再退回 cloud-api。
            # 之前这里写死 cloud-api, 导致 MTD_DEFAULT_LLM_MODEL=deepseek-chat 时平台仍是
            # cloud-api, 模型列表里没有 deepseek 于是静默退回第一个云模型。
            default_model = ctx.get("llm_model") or get_default_llm()

            def _platform_index_of(model: str) -> int:
                for i, name in enumerate(all_platforms):
                    if model in list(get_config_models(model_type="llm", platform_name=name)):
                        return i
                return next(
                    (i for i, name in enumerate(all_platforms) if name == "cloud-api"), 0
                )

            default_platform_idx = _platform_index_of(default_model)
            selected_platform = st.selectbox(
                "模型平台",
                all_platforms,
                index=default_platform_idx,
                key="platform",
            )
            llm_models = list(get_config_models(model_type="llm", platform_name=selected_platform))
            # 默认选中默认模型，该平台没有就取第一个
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
                # 注意: platform / llm_model 在上面侧边栏已经创建了对应的 widget,
                # Streamlit 规定 widget 实例化之后不能再写同名 session_state, 否则抛
                # StreamlitAPIException: "... cannot be modified after the widget with
                # key ... is instantiated" (点高级配置即崩)。
                # 这两项的当前值本来就已经在 session_state 中(由上面的 selectbox 写入),
                # 无需再同步; 只把尚未实例化的两项从会话上下文带过去即可。
                # 对话框内部是 @st.experimental_dialog(fragment) 独立一次运行,
                # 因此它复用 platform / llm_model 这两个 key 不会冲突。
                chat_box.context_to_session(include=["temperature", "system_message"])
                llm_model_setting()

        # 系统提示词显示
        with st.expander("📋 当前系统提示词"):
            system_prompt = build_teaching_system_prompt(
                st.session_state.get("teaching_mode", TEACHING_MODES[0]),
                st.session_state.get("selected_case")
            )
            st.text_area("系统提示词", system_prompt, height=200, disabled=True)
    
    # 主内容区域
    teaching_mode = st.session_state.get("teaching_mode", TEACHING_MODES[0])
    if teaching_mode not in TEACHING_MODES:
        teaching_mode = TEACHING_MODES[0]
    selected_case = st.session_state.get("selected_case")

    st.title("🤖 AI+MDT诊疗教学系统")

    if not selected_case:
        # 进门先选病例，而不是固定落在那一个默认病例上
        render_case_picker()
    else:
        render_case_header(selected_case, teaching_mode)
        teaching_mode = render_mode_steps()
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
        configured_history_len = st.session_state.get("mdt_history_len", 5)
        scope = "all" if st.session_state.get("mdt_kb_scope") == "全部文档" else "auto"

        # get_messages_history 会把 chat_box.context["system_message"] 顶到最前面，
        # 而下面我们自己拼 system（含知识库资料），这里把历史里的 system 去掉避免重复。
        history = [m for m in get_messages_history(configured_history_len) if m.get("role") != "system"]

        # 知识库用显式检索：读 content 目录、按病种关键词路由、整篇注入，不走向量库，
        # 因此不需要 ollama / 嵌入模型，改了文档立即生效。
        kb_context, kb_sources = "", []
        if selected_kb and selected_kb != "不使用知识库":
            kb_context, kb_sources = select_context(active_prompt, selected_kb, scope=scope)

        # 组装 messages。
        # 必须走 openai 兼容的 /v1/chat/completions：chatchat 自己的 /chat/chat/completions
        # 只把 messages 的最后一条当 query（见 server/api_server/chat_routes.py），system 提示
        # 与知识库资料会被静默丢掉——教学提示词此前一直没生效就是这个原因。
        system_content = build_teaching_system_prompt(teaching_mode, selected_case)
        if kb_context:
            system_content = f"{system_content}\n\n{kb_context}"
        messages = [{"role": "system", "content": system_content}]
        messages += history
        messages.append({"role": "user", "content": active_prompt})

        chat_box.user_say(active_prompt)

        if kb_context:
            chat_box.ai_say([
                Markdown(
                    sources_markdown(kb_sources),
                    in_expander=True,
                    title=f"资料「{selected_kb}」· 显式检索（未使用向量库）",
                    state="complete",
                ),
                "正在依据资料生成回答...",
            ])
        else:
            chat_box.ai_say("正在思考...")

        text = ""
        started = False
        last_message_id = ""

        client = openai.Client(
            base_url=f"{api_address()}/v1",
            api_key="NONE",
            timeout=100000,
            http_client=httpx.Client(trust_env=False),
        )

        params = dict(
            messages=messages,
            model=ctx.get("llm_model"),
            stream=True,
        )
        if Settings.model_settings.MAX_TOKENS:
            params["max_tokens"] = Settings.model_settings.MAX_TOKENS

        try:
            # /v1 是原样透传，返回标准 OpenAI 流式块（没有 status / message_id 字段）
            for chunk in client.chat.completions.create(**params):
                last_message_id = getattr(chunk, "id", "") or last_message_id
                delta = chunk.choices[0].delta.content if chunk.choices else ""
                if not delta:
                    continue
                if not started:
                    chat_box.update_msg("", streaming=False)
                    started = True
                text += delta
                chat_box.update_msg(
                    text.replace("\n", "\n\n"),
                    streaming=True,
                    metadata={"message_id": last_message_id},
                )
            chat_box.update_msg(
                text.replace("\n", "\n\n"),
                streaming=False,
                metadata={"message_id": last_message_id},
            )
        except Exception as e:
            st.error(str(e))
            chat_box.update_msg(f"抱歉，处理请求时出现错误：{str(e)}", streaming=False)
