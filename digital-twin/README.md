# PING digital twin

An independent Python project and GUI for experimenting with the PING rover.
It does not import or change the ground-station application, telemetry, or
camera. Each browser session owns its own simulation state and configuration.

## Open the GUI

From PowerShell, after a one-time installation:

```powershell
cd "C:\Users\alexc\Documents\GitHub\PING Project\digital-twin"
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m ping_twin
```

Later launches need only the `cd` and final command. The GUI opens at
<http://127.0.0.1:8081>. The 3D simulation sits between the **Geometry / Chassis**
controls on the left and **Powertrain / Terrain** controls on the right. Changes
apply live and are saved to `vehicle-settings.json` in this project; reopening
the GUI restores them. Use **W/S** for forward/reverse and **A/D** for steering;
the arrow keys work too. Pressing a drive key starts the simulation, while the
sliders and Run/Pause button remain available.
Keyboard driving releases when the page loses focus or a setting is edited.
Run/Pause/Reset affect only the current browser session.
Use **Inspect rover** above the 3D view to see the arm joints and dotted body
connections up close; **Show course** restores the terrain view.

The 50:1, 70:1 and 100:1 presets use Pololu's 12 V 37D helical-pinion output
specifications for items [4743](https://www.pololu.com/product/4743/specs),
[4744](https://www.pololu.com/product/4744/specs), and
[4745](https://www.pololu.com/product/4745/specs). The 100:1 model has an actual
102.08:1 ratio. Pololu's stall torque figures are extrapolated; this twin uses
them for a simplified torque/speed envelope, not a continuous-duty rating.

This is a reduced planar traction model, not a validated rigid-body or
suspension solver. Wheel speeds and body speed are independent states;
terrain contact force drives translation and wheel angular acceleration.
Pitch and roll are geometric ground truth from wheel contact heights. The arm
joints sit an adjustable sideways distance outside the body, with dotted links
back to the body sides. Wheel hubs share each joint's side plane, so the arms
run straight from joints to hubs. Wheel track is derived from body width and
the joint offset; front-to-rear axle spacing follows arm length and angles.
The amber CG marker sits at the centre of the translucent body box; its height
is derived from arm length and angles, not configured separately.
The sketch's `l1`, `w1`, and `h1`
are chassis length, width, and height. Obstacles are represented by blocking;
wheel lift, suspension compliance, tire deformation, and detailed rock shape
are not simulated.
