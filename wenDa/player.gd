extends CharacterBody3D

## 移动速度
@export var speed: float = 5.0
## 跳跃力度
@export var jump_velocity: float = 4.5
## 鼠标灵敏度
@export var mouse_sensitivity: float = 0.002
## 摄像机垂直旋转节点（如 SpringArm3D 或单独的一个 Marker3D）
@export var camera_pivot: Node3D
## 动画播放器
@export var animation_player: AnimationPlayer

var gravity: float = ProjectSettings.get_setting("physics/3d/default_gravity")


func _ready() -> void:
	Input.set_mouse_mode(Input.MOUSE_MODE_CAPTURED)


func _input(event: InputEvent) -> void:
	if event is InputEventMouseMotion and Input.get_mouse_mode() == Input.MOUSE_MODE_CAPTURED:
		rotate_y(-event.relative.x * mouse_sensitivity)

		if camera_pivot:
			camera_pivot.rotate_x(-event.relative.y * mouse_sensitivity)
			camera_pivot.rotation.x = clampf(camera_pivot.rotation.x, deg_to_rad(-80), deg_to_rad(60))

	if Input.is_action_just_pressed("ui_cancel"):
		if Input.get_mouse_mode() == Input.MOUSE_MODE_CAPTURED:
			Input.set_mouse_mode(Input.MOUSE_MODE_VISIBLE)
		else:
			Input.set_mouse_mode(Input.MOUSE_MODE_CAPTURED)


func _physics_process(delta: float) -> void:
	# 重力
	if not is_on_floor():
		velocity.y -= gravity * delta

	# 跳跃
	if Input.is_action_just_pressed("ui_accept") and is_on_floor():
		velocity.y = jump_velocity

	# WASD 移动
	var input_dir := Input.get_vector("move_left", "move_right", "move_forward", "move_backward")
	var direction := (transform.basis * Vector3(input_dir.x, 0, input_dir.y)).normalized()

	if direction:
		velocity.x = direction.x * speed
		velocity.z = direction.z * speed
	else:
		velocity.x = move_toward(velocity.x, 0, speed)
		velocity.z = move_toward(velocity.z, 0, speed)

	move_and_slide()

	# 动画
	_handle_animation(input_dir)


func _handle_animation(input_dir: Vector2) -> void:
	if not animation_player:
		return

	var is_moving := input_dir.length() > 0.1 and is_on_floor()

	if is_moving:
		if animation_player.has_animation("run"):
			if animation_player.current_animation != "run":
				animation_player.play("run")
		elif animation_player.has_animation("walk"):
			if animation_player.current_animation != "walk":
				animation_player.play("walk")
	else:
		if animation_player.has_animation("idle"):
			if animation_player.current_animation != "idle":
				animation_player.play("idle")
