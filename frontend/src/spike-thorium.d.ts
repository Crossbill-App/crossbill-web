// SPIKE #740 — throwaway. thorium-web's package exports map points
// `./reader/styles` and `./epub/styles` at .css files, which TS's bundler
// resolution refuses to accept as a side-effect import without a declaration.
declare module '@edrlab/thorium-web/reader/styles';
declare module '@edrlab/thorium-web/epub/styles';
