# A Lily Bouquet for Megan

A rotating 360-degree terminal bouquet with twelve lilies (six blue and six pink). The flower heads are scattered at different heights and depths; baby's breath and the ribbon are omitted so the lilies stand out.

The postcard text is kept simple:

> From Seth
>
> To Megan
>
> I love you.

## Run it

This uses Python 3.9+ and only Python's standard library. No packages need to be installed.

From this folder, run one still frame:

```bash
python3 lily_bouquet.py --once
```

Run the rotating bouquet:

```bash
python3 lily_bouquet.py
```

Press `Ctrl+C` to stop the animation. On Windows, use `python` in place of `python3` if that is how Python is installed.

Use a reasonably wide terminal window for the best layout. The animation uses ANSI 256-color terminal sequences.

## How it is made

The stems and wrapping paper rotate as 3D points. Twelve six-petal lily heads travel around the bouquet and face the viewer as they come around, with gold anthers to make the flower centers distinct. The full rotation reveals flowers from every side. Leaves are omitted for a cleaner silhouette.

