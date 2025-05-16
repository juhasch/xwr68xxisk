# Project Improvement Plan

This document outlines a plan for enhancing the radar application, focusing on GUI improvements, configuration management, visualization capabilities, and testing.

## Phase 1: Core Configuration and GUI Overhaul

### 1. Unify Program and Profile Configuration with Pydantic
    - **Goal:** Streamline configuration management using Pydantic and YAML files.
    - **Tasks:**
        - Define Pydantic models for all existing program settings and radar profile parameters.
            - *Note: The recent work on `SceneProfileConfig` (used for `.cfg` generation) directly supports this for radar profiles.*
            - *For "program settings," consider models for communication parameters (serial port, baud rate), data logging paths, and application settings (theme, logging verbosity).*
        - Refactor existing configuration loading/saving mechanisms to use these Pydantic models.
        - Implement loading configurations from YAML files and saving current configurations to YAML.
            - *Consider using `PyYAML` for standard needs or `ruamel.yaml` if comment preservation in YAML is important. Pydantic's `model_dump()` and `model_validate()` are key here.*
            - *Example (Conceptual):*
              ```python
              # Saving:
              # with open('config.yaml', 'w') as f:
              #     yaml.dump(pydantic_config_instance.model_dump(), f)
              # Loading:
              # with open('config.yaml', 'r') as f:
              #     data = yaml.safe_load(f)
              # validated_config = YourConfigModel.model_validate(data)
              ```
        - Ensure backward compatibility or a clear migration path if existing configuration formats change.
        - *Emphasize leveraging Pydantic's validation capabilities (e.g., `@field_validator`, `conint`, `confloat`) for data integrity.*
        - **Git Commit:** "feat: Unify configuration with Pydantic and YAML."

### 2. Redesign Profile Configuration GUI
    - **Goal:** Implement the new GUI for radar profile configuration as per the provided image (`configuration.png`).
    - **Tasks:**
        - Analyze the layout and components in `configuration.png`.
        - Identify necessary UI elements (sliders, dropdowns, input fields, checkboxes).
        - Choose appropriate Bokeh/Panel widgets for each element.
        - Develop the new GUI layout.
        - Connect GUI elements to the Pydantic configuration models. Changes in the GUI should update the model, and changes in the model (e.g., loading a profile) should reflect in the GUI.
            - *Explore `panel.Param` for tight integration with Pydantic models (if models inherit from `param.Parameterized`), potentially auto-generating UI or simplifying binding.*
        - Ensure the GUI dynamically updates interdependent fields (e.g., if a change in one parameter restricts the range of another).
            - *Pydantic's `@computed_field` and Panel's reactive nature can facilitate this at the model and GUI levels.*
        - Investigate using `pn.Modal` for dialogs for potential semantic correctness, while retaining the current `pn.Column` with CSS styling as a functional fallback.
            - *If using custom CSS for modals, ensure it's well-encapsulated to prevent style conflicts.*
        - **Git Commit:** "feat: Implement new profile configuration GUI."

### 3. Enhanced Configuration Management
    - **Goal:** Allow users to save, load, and manage named configuration profiles.
    - **Tasks:**
        - Design a system for naming, saving, and loading configuration profiles (both program and radar).
        - Implement GUI elements (e.g., dropdown to select a profile, save/load buttons) for managing these profiles.
        - Store profiles in a dedicated directory (e.g., `config/profiles/`) as YAML files.
        - *Consider implementing a "default" or "last used" profile feature on startup.*
        - *Ensure robust error handling for missing/corrupted profile files or schema mismatches.*
        - **Git Commit:** "feat: Add save/load functionality for named configuration profiles."

## Phase 2: Advanced Visualization and Plotting

### 4. Multi-Tab Visualization Interface
    - **Goal:** Create a tabbed interface to organize different plots and avoid UI clutter.
    - **Tasks:**
        - Design the tab structure. Consider how users will add, remove, and configure tabs.
        - Implement a Panel-based tab layout (e.g., `pn.Tabs`).
        - Allow users to select which plots appear in each tab.
        - Ensure plot configurations (e.g., plot type, data sources) are per-tab or globally configurable as appropriate.
            - *Consider how tab configurations (active plots, settings) will be managed and persisted, possibly within the main program settings or a separate "view configuration" model.*
        - **Git Commit:** "feat: Implement multi-tab visualization interface."

### 5. Implement New 2D Plot Types
    - **Goal:** Add new 2D plot types as requested.
    - **Tasks:**
        - **Range Profile Plot:**
            - Develop the logic to calculate and display signal strength vs. range.
            - Integrate into the multi-tab visualization system.
        - **Noise Profile Plot:**
            - Develop the logic to calculate and display noise level vs. range/Doppler.
            - Integrate into the multi-tab visualization system.
        - **Range Azimuth Heatmap:**
            - Develop the logic to generate and display a 2D heatmap of signal strength over range and azimuth.
            - Integrate into the multi-tab visualization system.
        - **Range Doppler Heatmap:**
            - Develop the logic to generate and display a 2D heatmap of signal strength over range and Doppler.
            - Integrate into the multi-tab visualization system.
        - For each plot:
            - *Strongly enforce separation of concerns: data processing logic (producing NumPy arrays/Pandas DataFrames) should be distinct from plotting code (consuming these structures with Bokeh/Panel).*
            - Ensure clear labeling, titles, and legends.
            - Allow basic customization (e.g., color maps for heatmaps).
                - *Store these user plot customizations as part of the program/view configuration to persist them.*
        - **Git Commit:** "feat: Add new 2D plot types (Range Profile, Noise Profile, Range-Azimuth, Range-Doppler)."

## Phase 3: 3D Visualization and Testing Infrastructure

### 7. Implement 3D Point Cloud Visualization
    - **Goal:** Display the point cloud in a 3D environment, integrated with the Panel/Bokeh GUI.
    - **Tasks:**
        - Research and select a suitable 3D rendering library compatible with Python/Bokeh/Panel (e.g., `PyVista`, `vedo`, or explore embedding `three.js` if feasible with Panel). Consider real-time performance.
            - *`PyVista` is a strong candidate; Panel provides `pn.pane.VTK` and `pn.pane.PyVista` for embedding.*
        - Develop the 3D scene setup (camera, lighting, axes).
        - Implement data mapping from the point cloud data (x, y, z, intensity) to the 3D renderer.
            - *Consider options to color/size points based on additional attributes (intensity, velocity) for richer visualization.*
        - Integrate the 3D view as a new plot type within a tab.
        - Ensure smooth real-time updates of the 3D point cloud.
            - *Investigate efficient data update mechanisms for the chosen library and Panel pane.*
        - Add basic 3D navigation controls (pan, zoom, rotate).
        - **Git Commit:** "feat: Implement initial 3D point cloud visualization."

### 8. Data Management and Testing with Pre-recorded Data
    - **Goal:** Improve testing capabilities by using pre-recorded radar data.
    - **Tasks:**
        - **Define Raw Data Format:**
            - Decide on a format for saving raw ADC data or processed detection data (e.g., HDF5, NumPy `.npz` with metadata).
            - Include necessary metadata (timestamp, sensor configuration).
                - *If using HDF5, define and document a clear schema. Store the full sensor configuration (`SceneProfileConfig` YAML/JSON dump) in the HDF5 metadata.*
        - **Implement Data Recording:**
            - Add functionality to save incoming raw data streams to the chosen format.
        - **Implement Data Replay:**
            - Create a mechanism to load recorded data and feed it into the processing pipeline as if it were live data.
                - *Consider if replay needs to mimic original data acquisition timing for testing real-time algorithms.*
            - This will allow testing the full pipeline without a connected radar.
        - **Create Test Cases:**
            - Develop `pytest` tests that use pre-recorded data to verify:
                - Correctness of processing algorithms.
                - Functionality of plot generation.
                - Consistency of outputs for known inputs.
                    - *The `pytest-regressions` plugin can be helpful for saving and comparing reference outputs.*
            - *Decide on a strategy for storing test data (e.g., `tests/data/`, possibly Git LFS for large files, though smaller representative datasets are preferable).*
        - **Git Commit:** "feat: Implement raw data recording/replay and initial tests with pre-recorded data."

## Phase 4: Refinement and Documentation

### 9. Code Refactoring for Modularity and Quality
    - **Goal:** Improve code structure, maintainability, and apply quality checks.
    - **Tasks:**
        - Review and refactor plotting components for better modularity.
        - Ensure clear separation of concerns (data acquisition, processing, GUI).
        - Run `ruff` for linting and auto-formatting. Address reported issues.
        - Review and enhance type hints and docstrings (Numpy style) throughout the codebase.
        - *Strongly consider setting up pre-commit hooks (`pre-commit` framework) to automatically run `ruff` (format & lint) and `mypy` before commits.*
            - *Example `.pre-commit-config.yaml` snippet:*
              ```yaml
              # repos:
              # -   repo: https://github.com/astral-sh/ruff-pre-commit
              #     rev: 'v0.x.y' # Use latest ruff version
              #     hooks:
              #     -   id: ruff
              #         args: [--fix, --exit-non-zero-on-fix]
              #     -   id: ruff-format
              # -   repo: https://github.com/pre-commit/mirrors-mypy
              #     rev: 'v1.x.y' # Use latest mypy version
              #     hooks:
              #     -   id: mypy
              #         args: [--strict]
              ```
        - **Git Commit:** "refactor: Improve code modularity and apply Ruff linting."

### 10. Performance Profiling and Optimization
    - **Goal:** Ensure the application runs smoothly, especially with real-time data and new visualizations.
    - **Tasks:**
        - Identify performance-critical sections (e.g., data processing, plot updates, 3D rendering).
        - Use profiling tools (e.g., `cProfile`, `line_profiler`) to measure execution time.
            - *Tools like `snakeviz` can provide interactive visualization for `cProfile` output.*
        - Optimize identified bottlenecks (e.g., algorithmic improvements, efficient library usage like NumPy vectorization).
            - *Prioritize optimization: 1. Algorithmic changes. 2. NumPy vectorization. 3. If extreme, `Numba` or `Cython`.*
        - **Git Commit:** "perf: Profile and optimize performance-critical sections."

### 11. Documentation Overhaul with Sphinx
    - **Goal:** Create comprehensive documentation for users and developers.
    - **Tasks:**
        - Set up Sphinx with necessary extensions (e.g., for Markdown (`myst-parser`), Napoleon for Numpy docstrings).
            - *Consider `sphinx-copybutton`, `sphinx_rtd_theme`, `sphinx-autodoc-typehints`.*
        - Write/update user guides for the new GUI, configuration, and visualization features.
            - *Include a "Quick Start" or "Tutorial" section.*
        - Generate API documentation from docstrings.
            - *Ensure `sphinx-apidoc` is configured to scan your source and generate API docs.*
        - Document the project structure and setup.
        - Add a section on how to use the pre-recorded data for testing.
        - *Consider hosting documentation online (Read the Docs, GitHub Pages).*
        - **Git Commit:** "docs: Overhaul documentation with Sphinx and Markdown."

### 12. Final Testing and Test Coverage
    - **Goal:** Ensure application stability and high test coverage.
    - **Tasks:**
        - Write additional unit and integration tests for new features and bug fixes.
            - *Unit tests for functions/methods; Integration tests for module interactions.*
            - *For Panel UI, test underlying models and methods triggered by UI events.*
        - Use `pytest-cov` to measure test coverage.
        - Aim for a high coverage percentage, focusing on critical components.
            - *Focus on critical paths, complex logic, and error handling routines.*
        - Perform thorough manual testing of all features.
        - **Git Commit:** "test: Increase test coverage and perform final testing."

## Ongoing Activities

- **Version Control:** Commit every major change or logical unit of work to Git with a clear and descriptive commit message.
- **Dependency Management:** Use `uv` to manage project dependencies. Maintain a `requirements.txt` or `pyproject.toml`.
    - *This is a good practice, aligned with modern Python packaging.*
- **Error Handling and Logging:** Continuously improve error handling and add contextual logging throughout the development process.
    - *Standardize on Python's `logging` module. Implement configurable log levels and allow output to console/files.*

This plan provides a structured approach to implementing the desired improvements. Each phase and task can be broken down further as development progresses. 