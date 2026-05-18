---
name: geogebra-master
description: Expert GeoGebra construction workflow for Claude Code, Codex, and other AI agents using the GeoGebra MCP server. Use when the user asks to draw or edit GeoGebra diagrams, graph functions, build Euclidean geometry, create 3D objects, use CAS-style algebra, make data/probability visuals, animate sliders, create mechanism sketches such as crank-rocker or slider-crank linkages, save .ggb files, export PNGs, or troubleshoot GeoGebra MCP connection/auto-launch problems. Also use when the user explicitly asks for geogebra_master.
---

# GeoGebra Master

Act as a precise GeoGebra operator through the `geogebra` MCP server. The goal is not just to send commands, but to design a robust construction that is ordered, inspectable, animated when useful, and saved/exported when requested.

This skill follows the official GeoGebra tutorial structure: Graphing, Geometry, 3D Graphics, CAS, Spreadsheet, Probability, and Advanced workflows. Choose the matching mode before issuing commands.

## First Contact

1. **Ask the user where to save output files before starting.** If the user hasn't specified an output directory or `.ggb` file path, ask: "Where should I save the .ggb file?" Do NOT proceed with construction until this is confirmed.
2. Call `geogebra_status` first for any real drawing task.
3. GeoGebra must already be running with `--remote-debugging-port=9222`. If status shows `connected: false`, tell the user: "Please start GeoGebra Classic 6 with remote debugging enabled: double-click `start_geogebra.bat` or run `GeoGebra.exe --remote-debugging-port=9222`. Then I'll continue."
4. If status still reports disconnected, suggest `geogebra-mcp-doctor`.
5. Call `geogebra_help` when uncertain about mechanism, animation, or command syntax.
6. Prefer structured tools:
   - Use `geogebra_create_construction` for complete named constructions.
   - Use `geogebra_run_commands` for ordered command batches.
   - Use `geogebra_exec` only for one-off commands or quick repair.
7. Verify with `geogebra_get_objects`, `geogebra_save`, or `geogebra_export_png`.

## Construction Order

Build in dependency order:

1. Set view with `geogebra_set_view`: `G` for 2D geometry/graphing, `AG` for algebra plus graphics, `3D` for 3D, `T` for tables.
2. Clear with `geogebra_new_construction` if the task asks for a fresh drawing.
3. Create base parameters, sliders, and fixed points.
4. Create dependent points, curves, lines, circles, intersections, surfaces, or data objects.
5. Draw visible segments, polygons, labels, traces, loci, and measurement objects.
6. Apply style with `geogebra_set_appearance`.
7. Start animation with `geogebra_animate` if there is a slider driver.
8. Save `.ggb` and export `.png` when the user asks for deliverables or when a visual check is useful.

Prefer ASCII object names and labels (`alpha`, `beta`, `O1`, `O2`, `crank`) unless the environment is known to preserve Unicode reliably.

## Command Idioms

Use these patterns as building blocks:

```text
A=(0,0)
B=(6,0)
f(x)=sin(x)
g(x)=cos(x)
l=Line(A,B)
s=Segment(A,B)
r=Ray(A,B)
c=Circle(A,2)
c2=Circle(A,B)
P=Intersect(c,c2,1)
M=Midpoint(A,B)
ang=Angle(A,O,B)
alpha=45 deg
P=O+(2*cos(alpha),2*sin(alpha))
Q=Rotate(P,alpha,O)
```

For sliders and animation, create a slider variable first, then define dependent objects from it:

```text
alpha=45 deg
O=(0,0)
A=O+(2*cos(alpha),2*sin(alpha))
trace=Circle(O,2)
```

Then call:

```json
{"label":"alpha","animate":true,"speed":0.5}
```

## Task Modes

### Graphing

Use graphing mode for functions, inequalities, intersections, derivatives, tangents, areas, and parametric curves. Prefer named functions and named intersection points.

Example:

```text
f(x)=sin(x)
g(x)=cos(x)
A=Intersect(f,g,1)
t=Tangent(A,f)
```

### Geometry

Use geometry mode for points, lines, circles, polygons, transformations, proofs-by-construction, loci, and measurements. Keep construction objects named and visible unless they are helper objects.

Example:

```text
A=(0,0)
B=(5,0)
C=(1.5,3)
tri=Polygon(A,B,C)
cc=Circle(A,B,C)
M=Midpoint(A,B)
```

### 3D Graphics

Use 3D mode for points in space, planes, spheres, polyhedra, vectors, surfaces, and spatial relationships. Set perspective to `3D` before creating 3D objects.

Example:

```text
A=(0,0,0)
B=(3,0,0)
C=(0,3,0)
s=Sphere(A,2)
plane=Plane(A,B,C)
```

### CAS And Algebra

Use CAS-style commands when the user asks to solve, simplify, factor, differentiate, integrate, or symbolically reason. Keep symbolic results visible in the algebra view when possible.

Example:

```text
f(x)=x^3-3x+1
df(x)=Derivative(f)
roots=Root(f)
```

### Data And Probability

Use spreadsheet/probability workflows for lists, histograms, distributions, regression, random samples, or probability visualizations. Use named lists and clear chart labels.

Example:

```text
L={1,2,2,3,5,8,13}
bar=BarChart(L)
mean=Mean(L)
```

### Advanced Animation

Use animation for sliders, mechanisms, dynamic traces, moving points, and demonstrations. Always animate a driver variable, not a static object.

Example:

```text
alpha=30 deg
O=(0,0)
P=O+(3*cos(alpha),3*sin(alpha))
path=Circle(O,3)
Segment(O,P)
```

Then call `geogebra_animate(label="alpha", animate=true, speed=0.5)`.

## Mechanism Patterns

For mechanisms, prefer the proven circle-intersection pattern. Validate geometry before drawing.

### ANIMATION IS MANDATORY FOR MECHANISMS

Every mechanism drawing MUST have an animated driver slider. Without this, the user sees a static diagram — NOT a mechanism. Follow these non-negotiable rules:

1. **Always create an angle slider as the FIRST command**: `alpha=30 deg` (or `θ=30 deg`, `φ=45 deg`). This creates a slider that cycles from 0° to 360°.
2. **Define moving joints using the slider**: `A=O1+(2*cos(alpha),2*sin(alpha))`. Points defined this way MOVE when the slider animates.
3. **After ALL commands, enable animation**: call `geogebra_animate(label="alpha", animate=true, speed=0.5)`. Without this call, the mechanism stays frozen.
4. **Verify animation is running**: the slider must be set to `animate=true`, not just created. A slider without `geogebra_animate` is a static number.

Crank-rocker:

```text
alpha=30 deg
O1=(0,0)
O2=(6,0)
A=O1+(2*cos(alpha),2*sin(alpha))
c1=Circle(A,5)
c2=Circle(O2,4)
B=Intersect(c1,c2,1)
ground=Segment(O1,O2)
crank=Segment(O1,A)
coupler=Segment(A,B)
rocker=Segment(B,O2)
```

Then call `geogebra_animate(label="alpha", animate=true, speed=0.5)`.

Slider-crank:

```text
alpha=30 deg
O=(0,0)
A=O+(2*cos(alpha),2*sin(alpha))
guide=Line((0,-2),(10,-2))
c=Circle(A,5)
B=Intersect(c,guide,1)
crank=Segment(O,A)
rod=Segment(A,B)
```

Then call `geogebra_animate(label="alpha", animate=true, speed=0.5)`.

Before presenting a mechanism as complete:

- **The angle slider `alpha` is created AND `geogebra_animate` was called.**
- Check the length constraints are possible.
- Use `Intersect(...,1)` or `Intersect(...,2)` deliberately.
- Verify object names with `geogebra_get_objects`.
- Save `.ggb` to the user-confirmed output path with `geogebra_save`.
- Export `.png` only if the user asked for a screenshot.

## Troubleshooting

If the MCP tool says `connected: false`:

1. Call `geogebra_status` once more after a short wait because auto-launch may still be starting.
2. Ask the user to run `geogebra-mcp-doctor` only if the status remains disconnected.
3. Explain likely causes: GeoGebra Classic 6 not installed, Node/npm missing, CDP port blocked, or an existing GeoGebra process was opened without the debugging port.
4. If there is an existing unsaved GeoGebra session, do not recommend restart until the user saves it.
5. If the user permits restart behavior, mention `GEOGEBRA_RESTART_EXISTING=1`.

If commands fail:

- Retry with simpler named intermediate objects.
- Avoid Unicode labels if encoding looks unstable.
- Use `geogebra_help(topic="commands")` or `geogebra_help(topic="mechanisms")`.
- Keep commands in dependency order and avoid referring to unnamed helper objects.

## Completion Checklist

Before saying the drawing is done:

- User's output path was confirmed before work started.
- The connection status was checked or the tool call succeeded.
- A fresh construction was used when appropriate.
- Commands were issued in dependency order.
- **For mechanisms: the angle slider is created AND `geogebra_animate` was called with `animate=true`.**
- Objects were verified or a saved/exported path was returned.
- Animation has a real slider driver if motion was requested.
- The `.ggb` file was saved to the user-confirmed output path.
- The response tells the user what was created and where files were saved.
