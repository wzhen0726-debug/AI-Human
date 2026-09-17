# 眼球绑Head骨 + 多动画重定向 (2026-09-03 验证)

## 眼球绑定到头骨(不飞天)
眼球对象(01A的Eye002_L/R, 世界位置如±0.036,-0.093,1.671)要跟头转动且位置不动。
- ❌ parent_type='BONE' + 手算matrix_parent_inverse → 眼球飞到头顶上方(z 1.671→1.908, 头顶才1.801)
- ❌ Child Of约束 + inverse_matrix抵消 → 更糟(z=3.342)
- ✅ 蒙皮法: `vg = o.vertex_groups.new(name='mixamorig:Head'); vg.add(list(range(len(o.data.vertices))), 1.0, 'REPLACE')` + Armature修改器(mod.object=arm, use_deform_preserve_volume=True)。位置不变, 跟头转。
- 验证: view_layer.update()后用 evaluated_get(dg).matrix_world.translation 对比绑定前后世界位置。
- 注意: 独立眼球物体走蒙皮不走顶点组改名, 批量给顶点组加mixamorig:前缀时跳过它无妨。

## 多动画重定向 (Mixamo FBX)
- **不同Mixamo FBX导出的参考骨架比例不同**: Standard Walk参考腿长0.893m, Running/Jump是0.955m。直接套会滑步。腿长比必须逐动画独立算: (我们Hips z−LeftFoot z)/(参考Hips z−参考LeftFoot z)。
- Hips垂直起伏: 逐帧读参考骨架Hips世界z(evaluated), (ref_z−ref_rest_z)×腿长比 → 写我们Hips局部y(此骨架局部y=世界垂直)。水平位移location全删, 原地动画。
- 贴地检测: 双脚Foot/Toe顶点组(weight>0.1)最低z>0.03算腾空。Walk必须0腾空; Running/Jump的离地期腾空是正常的, 需对比参考骨架离地状态区分。
- 03骨架保存时骨名无mixamorig:前缀(前缀在行走验证步才加), 套动画前要先给bones和顶点组补前缀。

## 多动作合并进一个blend (5.x动作系统坑)
- ❌ 删参考骨架/动作会连锁删掉action.copy()的副本(5.x新动作系统copy与原件共享数据) → 清理'Armature|mixamo...'后Running/Jump全丢。
- ❌ 改重命名原动作代替copy → 贴地检测全错(评估混乱), 回退。
- ✅ 验证过的合并流程:
  1. 逐动画: 导入FBX→copy action→重命名→适配→**立即删该参考骨架**(否则下个动画next()抓到旧骨架, 三个动画全是第一个的数据)
  2. 适配后的动作 use_fake_user=True
  3. **先保存**(3个命名动作落盘), 再删'Armature|'参考动作, 再保存; 最后assert剩余动作名集合==预期。
- 产物形态: 04_动作测试.blend一文件N动作, 动作编辑器下拉切换, 活跃动作=行走, 场景帧范围对齐行走。
- 脚本: 05骨骼绑定/ARP新版测试_20260831/scripts/merge_anims.py