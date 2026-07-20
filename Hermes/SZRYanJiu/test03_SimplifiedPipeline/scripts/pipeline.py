"""
Master Pipeline Controller — Simplified Quad Remesher Pipeline v3.
Reads config.json, runs stages sequentially with checkpoint support.
"""
import json, os, sys, subprocess, time, argparse
from datetime import datetime

class Pipeline:
    def __init__(self, config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            self.cfg = json.load(f)
        self.base = os.path.dirname(os.path.abspath(config_path))
        self.project_root = os.path.dirname(self.base)
        self.blender = self.cfg["pipeline"]["blender_path"]
        self.input_dir = os.path.join(self.project_root,
                                       self.cfg["pipeline"]["input_model"].split('/')[0])
        self.output_dir = os.path.join(self.project_root,
                                        self.cfg["pipeline"]["output_dir"])
        self.checkpoint_file = os.path.join(self.base, "checkpoint.json")
        self.checkpoint = self._load_checkpoint()

    def _load_checkpoint(self):
        if os.path.exists(self.checkpoint_file):
            with open(self.checkpoint_file, 'r') as f:
                return json.load(f)
        return {"completed": [], "last_run": None, "errors": {}}

    def _save_checkpoint(self):
        self.checkpoint["last_run"] = datetime.now().isoformat()
        with open(self.checkpoint_file, 'w') as f:
            json.dump(self.checkpoint, f, indent=2)

    def _run_blender(self, script, blend_path, extra_args, stage_name):
        """Run a Blender script in background mode."""
        cmd = [
            self.blender, blend_path, "--background",
            "--factory-startup",
            "--python", script, "--"
        ] + extra_args
        print(f"\n{'='*60}")
        print(f"[{stage_name}] Running: {' '.join(cmd)}")
        print(f"{'='*60}")

        result = subprocess.run(cmd, capture_output=True, text=True,
                                timeout=600)
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        if result.returncode != 0:
            raise RuntimeError(
                f"[{stage_name}] FAILED (exit {result.returncode}):\n{result.stderr}")
        return result

    def run_stage(self, stage_name):
        """Run a single stage, supporting resume from checkpoint."""
        if stage_name in self.checkpoint["completed"]:
            print(f"[{stage_name}] Already completed (checkpoint). Skipping.")
            return

        scripts_dir = self.base
        out_dir = os.path.join(self.output_dir, f"{self._stage_num(stage_name)}_{stage_name}")

        if not os.path.exists(out_dir):
            os.makedirs(out_dir, exist_ok=True)

        cfg = self.cfg.get(stage_name, {})
        blend_in = self._get_input_blend(stage_name)
        blend_out = os.path.join(out_dir, f"{stage_name}.blend")

        script = os.path.join(scripts_dir, f"{stage_name}.py")
        args = [f"--output={blend_out}"]
        args += self._build_args(stage_name, cfg)

        self._run_blender(script, blend_in, args, stage_name)
        self.checkpoint["completed"].append(stage_name)
        self._save_checkpoint()
        print(f"[{stage_name}] COMPLETED -> {blend_out}")

    def _stage_num(self, name):
        stages = self.cfg["pipeline"]["stages"]
        if name in stages:
            return f"{stages.index(name) + 1:02d}"
        return "00"

    def _get_input_blend(self, stage_name):
        """Determine input blend file for a stage."""
        stages = self.cfg["pipeline"]["stages"]
        idx = stages.index(stage_name)
        if idx == 0:
            # First stage: import from raw GLB
            glb_path = os.path.join(self.project_root,
                                     self.cfg["pipeline"]["input_model"])
            return self._import_glb_to_blend(glb_path, stage_name)
        else:
            # Previous stage's output
            prev = stages[idx - 1]
            prev_out = os.path.join(
                self.output_dir,
                f"{self._stage_num(prev)}_{prev}",
                f"{prev}.blend")
            return prev_out

    def _import_glb_to_blend(self, glb_path, stage_name):
        """Import GLB into a fresh blend file, return the blend path."""
        blend_out = os.path.join(self.output_dir,
                                  f"01_repair", "raw_import.blend")
        os.makedirs(os.path.dirname(blend_out), exist_ok=True)

        cmd = [
            self.blender, "--background", "--factory-startup",
            "--python-expr",
            f"import bpy; bpy.ops.import_scene.gltf(filepath='{glb_path}'); "
            f"bpy.ops.wm.save_as_mainfile(filepath='{blend_out}')"
        ]
        subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        return blend_out

    def _build_args(self, stage_name, cfg):
        """Build CLI args from config dict."""
        arg_map = {
            "repair": [
                f"--voxel_size={cfg.get('voxel_size', 0.005)}",
                f"--smooth_iter={cfg.get('smooth_iterations', 5)}",
                f"--smooth_factor={cfg.get('smooth_factor', 0.5)}",
            ],
            "adhesion": [
                f"--threshold={cfg.get('threshold_mm', 5.0)}",
                f"--push_step={cfg.get('push_step_mm', 0.5)}",
                f"--smooth_iter={cfg.get('smooth_iterations', 10)}",
                f"--smooth_factor={cfg.get('smooth_factor', 0.3)}",
            ],
            "remesh": [
                f"--target_count={cfg.get('target_count', 250000)}",
                f"--symmetry_x={cfg.get('use_symmetry_x', True)}",
                f"--hard_edges={cfg.get('detect_hard_edges', True)}",
                f"--adaptive_size={cfg.get('adaptive_size', True)}",
            ],
            "uv": [
                f"--angle={cfg.get('angle_threshold_deg', 55.0)}",
                f"--margin={cfg.get('island_margin', 0.005)}",
            ],
            "bake": [
                f"--image_size={cfg.get('image_size', 2048)}",
                f"--bake_distance={cfg.get('bake_distance', 0.02)}",
                f"--cage_extrusion={cfg.get('cage_extrusion', 0.01)}",
            ],
            "export_glb": [
                f"--output={os.path.join(self.output_dir, '07_glb', 'final.glb')}",
            ],
        }
        return arg_map.get(stage_name, [])

    def run_all(self, from_stage=None):
        """Run all stages in order, optionally resuming from a stage."""
        stages = self.cfg["pipeline"]["stages"]
        start = 0
        if from_stage and from_stage in stages:
            start = stages.index(from_stage)
        for stage in stages[start:]:
            self.run_stage(stage)

    def reset(self):
        """Clear checkpoint to force full re-run."""
        if os.path.exists(self.checkpoint_file):
            os.remove(self.checkpoint_file)
        self.checkpoint = {"completed": [], "last_run": None, "errors": {}}
        print("Checkpoint reset.")


def main():
    parser = argparse.ArgumentParser(description="Simplified Pipeline v3")
    parser.add_argument('--config', default=None,
                        help='Path to config.json')
    parser.add_argument('--stage', default=None,
                        help='Run a single stage (repair|adhesion|remesh|uv|bake|export_glb)')
    parser.add_argument('--from', dest='from_stage', default=None,
                        help='Resume from a specific stage')
    parser.add_argument('--reset', action='store_true',
                        help='Reset checkpoint')
    parser.add_argument('--list', action='store_true',
                        help='List stages and status')
    args = parser.parse_args()

    config_path = args.config or os.path.join(os.path.dirname(__file__),
                                               'config.json')
    if not os.path.exists(config_path):
        print(f"Config not found: {config_path}")
        sys.exit(1)

    p = Pipeline(config_path)

    if args.reset:
        p.reset()
    if args.list:
        print("Stages:", p.cfg["pipeline"]["stages"])
        print("Completed:", p.checkpoint["completed"])
        return
    if args.stage:
        p.run_stage(args.stage)
    elif args.from_stage:
        p.run_all(from_stage=args.from_stage)
    else:
        p.run_all()


if __name__ == "__main__":
    main()