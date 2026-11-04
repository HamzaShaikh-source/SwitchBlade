# SwitchBlade React Bits effects

This small React bundle mounts the free MicroSlats, TechText, and HoldButton components into the FastAPI UI. Build it with `npm ci && npm run build` from this directory. The generated `../assets/effects.js` and `../assets/effects.css` are served by FastAPI, so users do not need Node.js to run the app.

MicroSlats and TechText came from the source pasted by the project owner. HoldButton came from the [React Bits open-source repository](https://github.com/DavidHDev/react-bits), revision `4dc7b5b`, at `src/content/Micro/HoldButton/`. The relevant license notice is in [REACT_BITS_LICENSE.md](./REACT_BITS_LICENSE.md).

The [React Bits Pro Application UI](https://pro.reactbits.dev/docs/app-ui) source is not included because the project does not contain a Pro or Ultimate license. The product UI uses the available open-source effects where they serve the workflow.
