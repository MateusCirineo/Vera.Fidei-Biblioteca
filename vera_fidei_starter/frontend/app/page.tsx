// Render the presentation at the root as well as at `/apresentacao`.
// Besides being the natural public entry point, this keeps older installed
// service workers from receiving an opaque navigation redirect and falling
// back to the offline page before they can update themselves.
export { default } from './apresentacao/page'
