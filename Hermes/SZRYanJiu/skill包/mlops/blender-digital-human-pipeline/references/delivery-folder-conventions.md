# 交付文件夹整理规范 (05环节定型, 2026-09-03用户认可)

用户说"整理一下这个文件夹"时:
1. 对齐兄弟环节结构: 主产物.blend在根目录 + scripts/ + logs/ + README.md (+点位指南/测试记录等主题md)
2. 管线/自检脚本全移入scripts/; 删一次性diag_*脚本和被取代的过时脚本; 删*.blend1备份。
3. README.md写: 产物表、脚本表、用法命令、关键规则(血泪教训)。
4. 最终测试数据写入记录md; 整理后提交git+推送。logs/不入git。
5. Windows坑: bash里`2>nul`会在目录里生成字面`nul`文件, 导致git add报"error: open(...nul)"。用python删: os.remove("\\\\?\\"+绝对路径)。本项目已出现3次, 整理时顺手全仓扫。
6. 打点提示图: 用户自己在Blender GUI截图, 不要替他渲染标记点图(视口Empty不入渲染; 造mesh球也被拒)。