"""
共享保护块配置 — 供分析引擎和拆分引擎统一调用。

包含全部保护块 pattern 定义 + apply_protection_blocks() + _restore_placeholders()。
两边的 copy 已移至此文件，避免分叉。

用法:
    from _protection_config import apply_protection_blocks, _restore_placeholders
    protected, blocks = apply_protection_blocks(text)
    restored = _restore_placeholders(protected, blocks)
"""
import re

# ==================== 纯文本段落拆分：保护块 ====================
CN_NUM_FULL = r'[零一二三四五六七八九十百千万亿两〇廿卅卌]'

CONTACT_BLOCK_PATTERN = re.compile(
    rf'({CN_NUM_FULL}+、\s*(?:联系方式|联系人|联系电话|电话|传真|电子邮箱|邮箱|联系地址|地址)[\s\S]*?)'
    rf'(?=\n\s*{CN_NUM_FULL}+、|\n\s*第{CN_NUM_FULL}+[章条编节]|\Z)',
    re.IGNORECASE
)

DATE_PATTERN = re.compile(
    r'(二[〇零][二一二三四五六七八九]{2}年'
    r'[一二三四五六七八九十]+月'
    r'(?:[一二三四五六七八九十]+日)?)'
    r'|'
    r'(\d{4}\s*年\s*\d{1,2}\s*月\s*(?:\d{1,2}\s*日)?)'
    r'|'
    r'(\d{4}[-/]\d{1,2}[-/]\d{1,2})'
    r'|'
    r'(自\s*\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日起施行)'
    r'|'
    r'(\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日\s*至\s*\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日)'
)

DOC_NUM_PATTERN = re.compile(
    r'[\[〔]\s*\d{4}\s*[\]〕]\s*\d+\s*号'
    r'|'
    r'[一-鿿]+[\[〔]\d{4}[\]〕]\d+号'
)

PHONE_PATTERN = re.compile(
    r'(?<!\d)(?:0\d{2,3}[-]\d{7,8}|\d{3}[-]\d{4}[-]\d{4}|\d{11})(?!\d)'
)

BARE_YEAR_PATTERN = re.compile(r'(?:19|20)\d{2}\s*年')
SHORT_YEAR_PATTERN = re.compile(r'(?<!\d)\d\s*年(?!度)')

# 年份范围：覆盖 1949-2030（采用 analyze_split_types 版本，建国至今）
YEAR_RANGE_PATTERN = re.compile(
    r'(?<!\d)(?:19(?:4[9]|[5-9]\d)|20[0-2]\d|2030)(?!\d)'
)

# 版次引用中的数字点（如 "年版的6.1.3"、"本版的6.2.5.2"、"见6.1.10"）
VERSION_REF_PATTERN = re.compile(
    r'(?:年版的|本版的|见)\s*\d+(?:\.\d+)+'
)
NUM_HAO_PATTERN = re.compile(r'(?<!\d)\d+\s*号')
PERCENT_PATTERN = re.compile(r'\d+\.?\d*\s*[‰%]')
FRACTION_PATTERN = re.compile(r'(?<!\d)(\d+)\s*/\s*(\d+)(?=\s*(?:万|千|百|十|[一-鿿]|[,，。；;、]|$))')
UNIT_PATTERN = re.compile(r'\d+(?:\.\d+)?\s*[万米座个名次元]')
MONTH_DAY_PATTERN = re.compile(r'\d{1,2}\s*月\s*\d{1,2}\s*日')
MONTH_PATTERN = re.compile(r'(?<!\d)(?:1[0-2]|[1-9])\s*月')
QUARTER_PATTERN = re.compile(r'(?<!\d)[1-4]\s*季度')
RANGE_PATTERN = re.compile(r'\d+\s*至')
ITEM_PATTERN = re.compile(r'\d+\s*项')
# 数字+分（如 30分、5分），排除"分类"
MINUTE_PATTERN = re.compile(r'\d+\s*分(?!类)')
PAREN_RANGE_PATTERN = re.compile(r'[）)]\s*[至项]')

# 数字+表（如 1表、2表）
TABLE_X_PATTERN = re.compile(r'(?<!\d)\d+\s*表')
# 表+数字（如表1、表2）
X_TABLE_PATTERN = re.compile(r'表\s*\d+')
# 附件+数字（如 附件1、附件 2）
FJ_PATTERN = re.compile(r'附件\s*\d+')
FJ1_PATTERN = re.compile(r'附\s*\d+')
# 统一（防 统一、中一、被误识别为中文顿号）
TONGYI_PATTERN = re.compile(r'统\s*一')
# 合一（防 合一、中一、被误识别为中文顿号）
HEYI_PATTERN = re.compile(r'合\s*一')
BUYI_PATTERN = re.compile(r'不\s*一')
# 数字+毫米单位（如 5mm、10.5mm）
MM_PATTERN = re.compile(r'\d+(?:\.\d+)?\s*mm')
TEMP_C_PATTERN = re.compile(r'-?\d+(?:\.\d+)?\s*(?:°C|℃)')
DEGREE_PATTERN = re.compile(r'-?\d+(?:\.\d+)?\s*°')
ARC_MIN_PATTERN = re.compile(r'\d+\s*′')
HRC_PATTERN = re.compile(r'\d+\s*HRC')
MPA_PATTERN = re.compile(r'\d+(?:\.\d+)?\s*MPa')
M_PATTERN = re.compile(r'\d+(?:\.\d+)?\s*m(?!m|in)')
CM_PATTERN = re.compile(r'\d+(?:\.\d+)?\s*cm')
DM_PATTERN = re.compile(r'\d+(?:\.\d+)?\s*dm')
UM_PATTERN = re.compile(r'\d+(?:\.\d+)?\s*μm')
H_PATTERN = re.compile(r'\d+\s*h\b')
MIN2_PATTERN = re.compile(r'\d+\s*min\b')

# 图x — 图+编号（如图1、图2、图3-1、图5.2）
FIGURE_PATTERN = re.compile(
    r'图\s*\d+(?:\.\d+)*(?:\s*[-–—]\s*\d+(?:\.\d+)*)?'
)

# x部分 — 阿拉伯数字+部分（如 1部分、2部分）
PART_X_PATTERN = re.compile(
    r'\d+\s*部分'
)

# x千克 — 数字+千克（如 5千克、10.5千克）
KILOGRAM_PATTERN = re.compile(
    r'\d+(?:\.\d+)?\s*千克'
)

# x吨 — 数字+吨（如 3吨、100吨）
TON_PATTERN = re.compile(
    r'\d+(?:\.\d+)?\s*吨'
)

# x日内/月内/年内（如 3日内、5月内、1年内）
WITHIN_PATTERN = re.compile(r'\d+\s*[日月年周]\s*内')
# 数字+天（如 365天、366天），排除 "天气" "天然" "天津"
DAY_PATTERN = re.compile(
    r'\d+\s*天(?!气|然|津)'
)

# 数字+台（如 3台、5台），排除 "台式" "台灯" "台风" 等复合词
TAI_PATTERN = re.compile(
    r'(?<!\d)\d+(?:\.\d+)?\s*台(?!式|灯|风|高|号|阶|历|账|下|词|内|面)'
)

# 数字顿号序列（如 1、2、3、4、5）
DIGIT_ENUM_PATTERN = re.compile(r'\d+(?:、\s*\d+)+')
# 中文顿号序列（如 一、二、三、四、五）
##CN_ENUM_PATTERN = re.compile(r'[一二三四五六七八九十]+(?:、\s*[一二三四五六七八九十]+)+')
# 第一、第二、第三、第 等带第前缀的完整/不完整中文序列
DI_ENUM_PATTERN = re.compile(r'第[一二三四五六七八九十]+(?:、第[一二三四五六七八九十]+)*、第')
# x级（如 1级、2级）
LEVEL_PATTERN = re.compile(r'(?<!\d)\d+\s*级')
# m1（如 m1、m2）
M1_PATTERN = re.compile(r'm\d+')
# x瓶（如 1瓶、2瓶）
BOTTLE_PATTERN = re.compile(r'(?<!\d)\d+\s*瓶')
# x家（如 1家、2家），排除 家庭/家用/家园/家务/家人/家乡/家长/家属
FAMILY_PATTERN = re.compile(r'(?<!\d)\d+\s*家(?!庭|用|园|务|人|乡|长|属)')
# x人（如 1人、2人）
PERSON_PATTERN = re.compile(r'(?<!\d)\d+\s*人')
# x处（如 1处、2处）
PLACE_PATTERN = re.compile(r'(?<!\d)\d+\s*处')
# +x / -x（如 +1、-1、+二）
PLUSMINUS_PATTERN = re.compile(r'[+-][一二三四五六七八九十\d]+')
# x度（如 1度、45度）
DU_PATTERN = re.compile(r'(?<!\d)\d+(?:\.\d+)?\s*度')
# x份/件/箱/块/位（如 1份、2件、3箱、4块、5位）
UNIT2_PATTERN = re.compile(r'(?<!\d)\d+\s*[份件箱块位]')
# 条件x / 条件：x（如 条件1、条件：2）
CONDITION_PATTERN = re.compile(r'条件[：:]?\s*\d+(?!\.)')
# 说明x
##DESCRIPTION_PATTERN = re.compile(r'说明\d+(?!\.)')
# （中文数字）、序列如 （一）、（二）、（三）、
BRACKET_ENUM_PATTERN = re.compile(r'[（(][一二三四五六七八九十]+[）)](?:、[（(][一二三四五六七八九十]+[）)])+、?')
# x张（如 1张、2张）
ZHANG_PATTERN = re.compile(r'(?<!\d)\d+\s*张')
# x岁（如 1岁、18岁）
AGE_PATTERN = re.compile(r'(?<!\d)\d+\s*岁')
# 专栏x（如 专栏1、专栏2）
ZHUANLAN_PATTERN = re.compile(r'专栏\d+')
# 专项x（如 专项1、专项2）
ZHUANXIANG_PATTERN = re.compile(r'专项\d+')
# HxNx（如 H1N1、H7N9）
HXNX_PATTERN = re.compile(r'H\d+N\d+')
# x批（如 1批、2批）
BATCH_PATTERN = re.compile(r'(?<!\d)\d+\s*批')
# x倍（如 1倍、2倍、3倍）
TIMES_PATTERN = re.compile(r'(?<!\d)\d+(?:\.\d+)?\s*倍')
# x剂（如 1剂、2剂），排除 "剂量"
JI_PATTERN = re.compile(r'(?<!\d)\d+\s*剂(?!量)')
# 00x/000x 零填充序号（如 001、0001）
ZPAD_PATTERN = re.compile(r'0{2,}\d+')
# 均一（防误识别）
JUNYI_PATTERN = re.compile(r'均\s*一')
# 唯一（防误识别）
WEIYI_PATTERN = re.compile(r'唯\s*一')
# 科目x（如 科目一、科目二、科目1）
KEMU_PATTERN = re.compile(r'科目[一二三四五六七八九十\d]+')
# 罗马数字（全角 ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩⅪⅫ）
ROMAN_PATTERN = re.compile(r'(?:[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩⅪⅫ]+|(?<![A-Za-z_])[IVXLCDM]+(?![A-Za-z_]))')
# 第x列
LIE_PATTERN = re.compile(r'第\s*\d+\s*列')
# 第x款
KUAN_PATTERN = re.compile(r'第\s*[一二三四五六七八九十\d]+\s*款')
# 第x节（数字点版 如 第3.1节）
DOTTED_JIE_PATTERN = re.compile(r'第\d+(?:\.\d+)+\s*节')
# 第x段
DUAN_PATTERN = re.compile(r'第\s*[一二三四五六七八九十\d]+\s*段')
XIAOSHI_PATTERN = re.compile(r'(?<!\d)\d+\s*小时')
KE_PATTERN = re.compile(r'(?<!\d)\d+\s*克(?!服|制)')
CHANGZIMU_PATTERN = re.compile(r'\d+[A-Za-z]+')
MILILITER_PATTERN = re.compile(r'(?<!\d)\d+\s*毫升')
ZHONG_PATTERN = re.compile(r'(?<!\d)\d+\s*种(?!类|族)')
MILIGRAM_PATTERN = re.compile(r'(?<!\d)\d+\s*毫克')
TAO_PATTERN = re.compile(r'(?<!\d)\d+\s*套')
PIAN_PATTERN = re.compile(r'(?<!\d)\d+\s*篇')
TRRILION_PATTERN = re.compile(r'(?<!\d)\d+\s*亿元')
ZI_PATTERN = re.compile(r'(?<!\d)\d+\s*字')
LEI_PATTERN = re.compile(r'(?<!\d)\d+\s*类(?!别|型|似|比)')
MOKUAI_PATTERN = re.compile(r'(?<!\d)\d+\s*模块')
def apply_protection_blocks(text):
    """在分析前替换非结构性内容为占位符。返回 (protected_text, blocks)。"""
    blocks = []



    def _buyi_repl(m):
        blocks.append(m.group(0))
        return f"___PB_BUYI_{len(blocks)}___"
    text = BUYI_PATTERN.sub(_buyi_repl, text)
    def _mokuai_repl(m):
        blocks.append(m.group(0))
        return f"___PB_MOKUAI_{len(blocks)}___"
    text = MOKUAI_PATTERN.sub(_mokuai_repl, text)
    def _lei_repl(m):
        blocks.append(m.group(0))
        return f"___PB_LEI_{len(blocks)}___"
    text = LEI_PATTERN.sub(_lei_repl, text)
    def _zi_repl(m):
        blocks.append(m.group(0))
        return f"___PB_ZI_{len(blocks)}___"
    text = ZI_PATTERN.sub(_zi_repl, text)
    def _trrilion_repl(m):
        blocks.append(m.group(0))
        return f"___PB_TRRILION_{len(blocks)}___"
    text = TRRILION_PATTERN.sub(_trrilion_repl, text)
    def _pian_repl(m):
        blocks.append(m.group(0))
        return f"___PB_PIAN_{len(blocks)}___"
    text = PIAN_PATTERN.sub(_pian_repl, text)
    def _fj1_repl(m):
        blocks.append(m.group(0))
        return f"___PB_FJ1_{len(blocks)}___"
    text = FJ1_PATTERN.sub(_fj1_repl, text)
    
    def _zhong_repl(m):
        blocks.append(m.group(0))
        return f"___PB_ZHONG_{len(blocks)}___"
    text = ZHONG_PATTERN.sub(_zhong_repl, text)
    def _tao_repl(m):
        blocks.append(m.group(0))
        return f"___PB_TAO_{len(blocks)}___"
    text = TAO_PATTERN.sub(_tao_repl, text)

    def _miligram_repl(m):
        blocks.append(m.group(0))
        return f"___PB_MILIGRAM_{len(blocks)}___"
    text = MILIGRAM_PATTERN.sub(_miligram_repl, text)

    def _changzimu_repl(m):
        blocks.append(m.group(0))
        return f"___PB_CHANGZIMU_{len(blocks)}___"
    text = CHANGZIMU_PATTERN.sub(_changzimu_repl, text)

    def _mililiter_repl(m):
        blocks.append(m.group(0))
        return f"___PB_MILILITER_{len(blocks)}___"
    text = MILILITER_PATTERN.sub(_mililiter_repl, text)

    def _ke_repl(m):
        blocks.append(m.group(0))
        return f"___PB_KE_{len(blocks)}___"
    text = KE_PATTERN.sub(_ke_repl, text)

    def _xiaoshi_repl(m):
        blocks.append(m.group(0))
        return f"___PB_XIAOSHI_{len(blocks)}___"
    text = XIAOSHI_PATTERN.sub(_xiaoshi_repl, text)
    def _date_repl(m):
        blocks.append(m.group(0))
        return f"___PB_DATE_{len(blocks)}___"
    text = DATE_PATTERN.sub(_date_repl, text)

    def _doc_repl(m):
        blocks.append(m.group(0))
        return f"___PB_DOC_{len(blocks)}___"
    text = DOC_NUM_PATTERN.sub(_doc_repl, text)

    def _phone_repl(m):
        blocks.append(m.group(0))
        return f"___PB_PHONE_{len(blocks)}___"
    text = PHONE_PATTERN.sub(_phone_repl, text)

    def _contact_repl(m):
        blocks.append(m.group(0))
        return f"___PB_CONTACT_{len(blocks)}___"
    text = CONTACT_BLOCK_PATTERN.sub(_contact_repl, text)

    def _year_repl(m):
        blocks.append(m.group(0))
        return f"___PB_YEAR_{len(blocks)}___"
    text = BARE_YEAR_PATTERN.sub(_year_repl, text)

    def _sy_repl(m):
        blocks.append(m.group(0))
        return f"___PB_SY_{len(blocks)}___"
    text = SHORT_YEAR_PATTERN.sub(_sy_repl, text)

    def _yr_repl(m):
        blocks.append(m.group(0))
        return f"___PB_YR_{len(blocks)}___"
    text = YEAR_RANGE_PATTERN.sub(_yr_repl, text)

    # 版次引用 → ___PB_VER_N___
    def _ver_repl(m):
        blocks.append(m.group(0))
        return f"龘___PB_VER_{len(blocks)}___"
    text = VERSION_REF_PATTERN.sub(_ver_repl, text)

    def _hao_repl(m):
        blocks.append(m.group(0))
        return f"___PB_HAO_{len(blocks)}___"
    text = NUM_HAO_PATTERN.sub(_hao_repl, text)

    def _pct_repl(m):
        blocks.append(m.group(0))
        return f"___PB_PCT_{len(blocks)}___"
    text = PERCENT_PATTERN.sub(_pct_repl, text)

    def _frac_repl(m):
        blocks.append(m.group(0))
        return f"___PB_FRAC_{len(blocks)}___"
    text = FRACTION_PATTERN.sub(_frac_repl, text)

    def _unit_repl(m):
        blocks.append(m.group(0))
        return f"___PB_UNIT_{len(blocks)}___"
    text = UNIT_PATTERN.sub(_unit_repl, text)

    def _md_repl(m):
        blocks.append(m.group(0))
        return f"___PB_MD_{len(blocks)}___"
    text = MONTH_DAY_PATTERN.sub(_md_repl, text)

    def _mo_repl(m):
        blocks.append(m.group(0))
        return f"___PB_MO_{len(blocks)}___"
    text = MONTH_PATTERN.sub(_mo_repl, text)

    def _qt_repl(m):
        blocks.append(m.group(0))
        return f"___PB_QT_{len(blocks)}___"
    text = QUARTER_PATTERN.sub(_qt_repl, text)

    def _range_repl(m):
        blocks.append(m.group(0))
        return f"___PB_RANGE_{len(blocks)}___"
    text = RANGE_PATTERN.sub(_range_repl, text)

    def _item_repl(m):
        blocks.append(m.group(0))
        return f"___PB_ITEM_{len(blocks)}___"
    text = ITEM_PATTERN.sub(_item_repl, text)

    # 数字+分 时间/评分表达式（如 30分、5分）
    def _min_repl(m):
        blocks.append(m.group(0))
        return f"___PB_MIN_{len(blocks)}___"
    text = MINUTE_PATTERN.sub(_min_repl, text)

    def _pr_repl(m):
        blocks.append(m.group(0))
        return f"___PB_PR_{len(blocks)}___"
    text = PAREN_RANGE_PATTERN.sub(_pr_repl, text)

    def _tx_repl(m):
        blocks.append(m.group(0))
        return f"龘___PB_TX_{len(blocks)}___"
    text = TABLE_X_PATTERN.sub(_tx_repl, text)

    def _xt_repl(m):
        blocks.append(m.group(0))
        return f"龘___PB_XT_{len(blocks)}___"
    text = X_TABLE_PATTERN.sub(_xt_repl, text)

    # 附件 → 龘___PB_FJ_N___
    def _fj_repl(m):
        blocks.append(m.group(0))
        return f"龘___PB_FJ_{len(blocks)}___"
    text = FJ_PATTERN.sub(_fj_repl, text)

    def _ty_repl(m):
        blocks.append(m.group(0))
        return f"龘___PB_TY_{len(blocks)}___"
    text = TONGYI_PATTERN.sub(_ty_repl, text)

    def _hy_repl(m):
        blocks.append(m.group(0))
        return f"龘___PB_HY_{len(blocks)}___"
    text = HEYI_PATTERN.sub(_hy_repl, text)

    def _mm_repl(m):
        blocks.append(m.group(0))
        return f"___PB_MM_{len(blocks)}___"
    text = MM_PATTERN.sub(_mm_repl, text)

    def _tc_repl(m):
        blocks.append(m.group(0))
        return f"___PB_TC_{len(blocks)}___"
    text = TEMP_C_PATTERN.sub(_tc_repl, text)

    def _deg_repl(m):
        blocks.append(m.group(0))
        return f"___PB_DEG_{len(blocks)}___"
    text = DEGREE_PATTERN.sub(_deg_repl, text)

    # 角分 → 龘___PB_AM_N___
    def _am_repl(m):
        blocks.append(m.group(0))
        return f"龘___PB_AM_{len(blocks)}___"
    text = ARC_MIN_PATTERN.sub(_am_repl, text)

    def _hrc_repl(m):
        blocks.append(m.group(0))
        return f"___PB_HRC_{len(blocks)}___"
    text = HRC_PATTERN.sub(_hrc_repl, text)

    def _mpa_repl(m):
        blocks.append(m.group(0))
        return f"___PB_MPA_{len(blocks)}___"
    text = MPA_PATTERN.sub(_mpa_repl, text)

    def _m_repl(m):
        blocks.append(m.group(0))
        return f"___PB_M_{len(blocks)}___"
    text = M_PATTERN.sub(_m_repl, text)

    def _cm_repl(m):
        blocks.append(m.group(0))
        return f"___PB_CM_{len(blocks)}___"
    text = CM_PATTERN.sub(_cm_repl, text)

    def _dm_repl(m):
        blocks.append(m.group(0))
        return f"___PB_DM_{len(blocks)}___"
    text = DM_PATTERN.sub(_dm_repl, text)

    def _um_repl(m):
        blocks.append(m.group(0))
        return f"___PB_UM_{len(blocks)}___"
    text = UM_PATTERN.sub(_um_repl, text)

    def _h_repl(m):
        blocks.append(m.group(0))
        return f"___PB_H_{len(blocks)}___"
    text = H_PATTERN.sub(_h_repl, text)

    # 分钟 → 龘___PB_MIN2_N___
    def _min2_repl(m):
        blocks.append(m.group(0))
        return f"龘___PB_MIN2_{len(blocks)}___"
    text = MIN2_PATTERN.sub(_min2_repl, text)

    def _fig_repl(m):
        blocks.append(m.group(0))
        return f"龘___PB_FIG_{len(blocks)}___"
    text = FIGURE_PATTERN.sub(_fig_repl, text)

    def _px_repl(m):
        blocks.append(m.group(0))
        return f"龘___PB_PX_{len(blocks)}___"
    text = PART_X_PATTERN.sub(_px_repl, text)

    def _kg_repl(m):
        blocks.append(m.group(0))
        return f"龘___PB_KG_{len(blocks)}___"
    text = KILOGRAM_PATTERN.sub(_kg_repl, text)

    def _ton_repl(m):
        blocks.append(m.group(0))
        return f"龘___PB_TON_{len(blocks)}___"
    text = TON_PATTERN.sub(_ton_repl, text)

    def _win_repl(m):
        blocks.append(m.group(0))
        return f"___PB_WITHIN_{len(blocks)}___"
    text = WITHIN_PATTERN.sub(_win_repl, text)

    def _day_repl(m):
        blocks.append(m.group(0))
        return f"___PB_DAY_{len(blocks)}___"
    text = DAY_PATTERN.sub(_day_repl, text)

    def _tai_repl(m):
        blocks.append(m.group(0))
        return f"龘___PB_TAI_{len(blocks)}___"
    text = TAI_PATTERN.sub(_tai_repl, text)

    # 数字顿号序列 → 龘___PB_DE_N___
    def _de_repl(m):
        blocks.append(m.group(0))
        return f"龘___PB_DE_{len(blocks)}___"
    text = DIGIT_ENUM_PATTERN.sub(_de_repl, text)

    # 中文顿号序列 → 龘___PB_CE_N___
    ##def _ce_repl(m):
    ##    blocks.append(m.group(0))
    ##    return f"龘___PB_CE_{len(blocks)}___"
    ##text = CN_ENUM_PATTERN.sub(_ce_repl, text)

    # 第x序列 → 龘___PB_DI_N___
    def _di_repl(m):
        blocks.append(m.group(0))
        return f"龘___PB_DI_{len(blocks)}___"
    text = DI_ENUM_PATTERN.sub(_di_repl, text)

    def _lv_repl(m):
        blocks.append(m.group(0))
        return f"龘___PB_LV_{len(blocks)}___"
    text = LEVEL_PATTERN.sub(_lv_repl, text)

    def _m1_repl(m):
        blocks.append(m.group(0))
        return f"龘___PB_M1_{len(blocks)}___"
    text = M1_PATTERN.sub(_m1_repl, text)

    def _bt_repl(m):
        blocks.append(m.group(0))
        return f"___PB_BT_{len(blocks)}___"
    text = BOTTLE_PATTERN.sub(_bt_repl, text)

    def _fml_repl(m):
        blocks.append(m.group(0))
        return f"___PB_FML_{len(blocks)}___"
    text = FAMILY_PATTERN.sub(_fml_repl, text)

    def _per_repl(m):
        blocks.append(m.group(0))
        return f"___PB_PER_{len(blocks)}___"
    text = PERSON_PATTERN.sub(_per_repl, text)

    def _plc_repl(m):
        blocks.append(m.group(0))
        return f"___PB_PLC_{len(blocks)}___"
    text = PLACE_PATTERN.sub(_plc_repl, text)

    def _pm_repl(m):
        blocks.append(m.group(0))
        return f"___PB_PM_{len(blocks)}___"
    text = PLUSMINUS_PATTERN.sub(_pm_repl, text)

    def _du_repl(m):
        blocks.append(m.group(0))
        return f"___PB_DU_{len(blocks)}___"
    text = DU_PATTERN.sub(_du_repl, text)

    def _u2_repl(m):
        blocks.append(m.group(0))
        return f"___PB_U2_{len(blocks)}___"
    text = UNIT2_PATTERN.sub(_u2_repl, text)

    # 条件x/条件：x → 龘___PB_COND_N___
    def _cond_repl(m):
        blocks.append(m.group(0))
        return f"龘___PB_COND_{len(blocks)}___"
    text = CONDITION_PATTERN.sub(_cond_repl, text)

    # 说明x → 龘___PB_DESC_N___
    ##def _desc_repl(m):
    ##    blocks.append(m.group(0))
    ##    return f"龘___PB_DESC_{len(blocks)}___"
    ##text = DESCRIPTION_PATTERN.sub(_desc_repl, text)

    # （一）、（二）、（三）、序列 → 龘___PB_BRENUM_N___
    def _brenum_repl(m):
        blocks.append(m.group(0))
        return f"龘___PB_BRENUM_{len(blocks)}___"
    text = BRACKET_ENUM_PATTERN.sub(_brenum_repl, text)

    def _zhang_repl(m):
        blocks.append(m.group(0))
        return f"___PB_ZHANG_{len(blocks)}___"
    text = ZHANG_PATTERN.sub(_zhang_repl, text)

    def _age_repl(m):
        blocks.append(m.group(0))
        return f"___PB_AGE_{len(blocks)}___"
    text = AGE_PATTERN.sub(_age_repl, text)

    # 专栏x → 龘___PB_ZL_N___
    def _zl_repl(m):
        blocks.append(m.group(0))
        return f"龘___PB_ZL_{len(blocks)}___"
    text = ZHUANLAN_PATTERN.sub(_zl_repl, text)

    # 转向x → 龘___PB_ZX_N___
    def _zx_repl(m):
        blocks.append(m.group(0))
        return f"龘___PB_ZX_{len(blocks)}___"
    text = ZHUANXIANG_PATTERN.sub(_zx_repl, text)

    def _hxnx_repl(m):
        blocks.append(m.group(0))
        return f"___PB_HXNX_{len(blocks)}___"
    text = HXNX_PATTERN.sub(_hxnx_repl, text)

    def _btch_repl(m):
        blocks.append(m.group(0))
        return f"___PB_BTCH_{len(blocks)}___"
    text = BATCH_PATTERN.sub(_btch_repl, text)

    def _tm_repl(m):
        blocks.append(m.group(0))
        return f"___PB_TM_{len(blocks)}___"
    text = TIMES_PATTERN.sub(_tm_repl, text)

    def _ji_repl(m):
        blocks.append(m.group(0))
        return f"___PB_JI_{len(blocks)}___"
    text = JI_PATTERN.sub(_ji_repl, text)

    def _zpad_repl(m):
        blocks.append(m.group(0))
        return f"___PB_ZPAD_{len(blocks)}___"
    text = ZPAD_PATTERN.sub(_zpad_repl, text)

    # 均一 → 龘___PB_JY_N___
    def _jy_repl(m):
        blocks.append(m.group(0))
        return f"龘___PB_JY_{len(blocks)}___"
    text = JUNYI_PATTERN.sub(_jy_repl, text)

    # 唯一 → 龘___PB_WY_N___
    def _wy_repl(m):
        blocks.append(m.group(0))
        return f"龘___PB_WY_{len(blocks)}___"
    text = WEIYI_PATTERN.sub(_wy_repl, text)

    # 科目x → 龘___PB_KM_N___
    def _km_repl(m):
        blocks.append(m.group(0))
        return f"龘___PB_KM_{len(blocks)}___"
    text = KEMU_PATTERN.sub(_km_repl, text)

    # 罗马数字 → 龘___PB_ROMAN_N___
    def _roman_repl(m):
        blocks.append(m.group(0))
        return f"龘___PB_ROMAN_{len(blocks)}___"
    text = ROMAN_PATTERN.sub(_roman_repl, text)

    def _lie_repl(m):
        blocks.append(m.group(0))
        return f"龘___PB_LIE_{len(blocks)}___"
    text = LIE_PATTERN.sub(_lie_repl, text)

    def _kuan_repl(m):
        blocks.append(m.group(0))
        return f"龘___PB_KUAN_{len(blocks)}___"
    text = KUAN_PATTERN.sub(_kuan_repl, text)

    def _djie_repl(m):
        blocks.append(m.group(0))
        return f"龘___PB_DJIE_{len(blocks)}___"
    text = DOTTED_JIE_PATTERN.sub(_djie_repl, text)

    def _duan_repl(m):
        blocks.append(m.group(0))
        return f"龘___PB_DUAN_{len(blocks)}___"
    text = DUAN_PATTERN.sub(_duan_repl, text)

    return text, blocks


def _restore_placeholders(text, blocks):
    """将 ___PB_XXX_N___ 占位符还原为原始内容。"""
    if not blocks:
        return text
    def _repl(m):
        idx = int(m.group(1)) - 1
        return blocks[idx] if 0 <= idx < len(blocks) else m.group(0)
    text = text.replace('龘', '')
    text = re.sub(r'___PB_[A-Z0-9]+_(\d+)___', _repl, text)
    return text
