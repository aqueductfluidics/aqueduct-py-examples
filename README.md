- [Introduction](#introduction)
- [Nomenclature](#nomenclature)
- [Usage](#usage)
    - [Uploading a Library](#uploading-library)
    - [Modifying or Extending a Library](#modifying-library)
    - [Using Recipe Code](#using-recipe-code)
- [Contact](#contact)

# Introduction #

This repository contains:

- **Libraries** (`/local/lib` directory), which include application-specific Python classes and methods.

- **Recipe Script** files (`/local/recipes` directory), which include Python scripts intended to be executed in the Aqueduct platform.
These Python scripts depend on the Library of the same name (for example, scripts in the `/local/recipes/ph_control`
path require the `/local/lib/ph_control` Library)

- **Recipe** (`.recipe`), **Setup** (`.setup`), and **Layout** (`.aq-layout`) files
(`/files/recipes` directory, `/files/setups` directory, `/files/layouts` directory, respectively), which contain files
that can be uploaded to an Aqueduct Hub and used to load a `.recipe`, `.setup`, or `.aq-layout`.

# Q&A on Nomenclature

* What is a Library?

    A: A **Library** is a collection of related Python classes and methods. We've grouped the
    libraries by application (for instance, `ph_control` or `filtration`). Libraries
    are intended to allow for reuse of common functionality across multiple Recipes.

* What is a Recipe Script?

    A: A **Recipe Script** is simply a Python file (`.py`) that is run in the Aqueduct environment.
    It contains the logic to execute your process. A Recipe Script can import from one
    or more local Libraries and the standard Python library.

* What is a Recipe file?

    A: A **Recipe** file (`.recipe` extension) contains a Recipe Script, a Setup, and (optionally) a Layout. It contains
    all of the data necessary to recreate a user interface (Device, Container, and Connection icon arrangement
    and Widget layout and metadata) and the logic (contained in the Recipe Script) to execute a protocol or processs.

* What is a Setup file?

    A: A **Setup** file (`.setup` extension) contains the type and number of Devices (such as pumps, valves, or sensors),
    Containers (such as beakers, vials, or other labware), Connections (a representation of tubing,
    both external and internal to Devices or Containers), and Inserts (alignment guides for
    robotic arms). It also contains the layout of the icons to generate the user interface.

* What is a Layout file?

    A: A **Layout** file (`.aq-layout` extension) contains arrangement of Widgets and Widget metadata that generate the
    user interface. For instance, the specific data series that are plotted on the Chart Widget on Tab 1
    is stored in a layout file. You can tailor the Layout arrangement to your preferences and save
    the configuration as a Layout file for reuse later.

In summary:

A Recipe (`.recipe` file), contains a Recipe Script, Setup, and (maybe) a Layout. When a Recipe
is run in the Aqueduct platform, it executes the code found in the Recipe Script. A Recipe Script
may import classes, methods, or definitions from one or more local Libraries.

# Usage #

## <a id="uploading-library"></a>Uploading a Library ##

If you would like to use a Library on your Hub, we suggest you clone this repository
on your local machine. Next, compress the Library in .zip format and upload it
to your Hub using the dashboard.

For example, if you wish to upload the `ph_control` Library:

1. Clone this repository
2. Zip the directory `/local/lib/ph_control` to a compressed folder named `ph_control.zip`
3. Upload `ph_control.zip` to your Hub, where it will appear in the tree of Local Libraries

## <a id="modifying-library"></a>Modifying or Extending a Library ##

If you would like to make changes or extensions to one of the Libraries in this repository,
we suggest that you follow the same steps in the [Uploading a Library](#uploading-a-library) Section
to clone the repository.

Next, make changes to the files in the target library as desired in your favorite code editor or IDE.

Once you're ready to use your new Library, follow the steps to compress and upload the Library to your Hub.

## <a id="using-recipe-code"></a>Using Recipe Code ##

Python files (`.py`) in the the `/local/recipes` directory are intended to be copied directly
into the Recipe Editor in the Aqueduct software application. Make sure that you have installed any
Library dependecies necessary to use the script. For example, scripts in the `/local/recipes/ph_control`
directory require the `/local/lib/ph_control` Library. In addition, make sure that any Devices
required by the Recipe are present in the Setup. For instance, it the script utilizes a peristaltic
pump (Device type **PP**) named `PPSIM`, then this device must be present in the Setup when the
Recipe is queued or it will fail.

# Contact #

See a bug or typo? Are you interested in using the platform?

Contact us at <info@aqueductfluidics.com>
