var webpack = require('webpack')
module.exports = {
  context: __dirname + "/caselink/static/javascript",
  entry: {
    // The script that will load before page loaded.
    head: './pack/pace.js',
    // Common lib
    include: ['jquery', 'bootstrap-webpack', 'font-awesome-webpack', './pack/datatables.js', './pack/style.js'],
    // Pages
    a2m: './a2m.js',
    m2a: './m2a.js',
    index: './index.js',
  },
  output: {
    path: __dirname + '/caselink/static/dist/',
    publicPath: '/static/dist/',
    filename: "[name].js"
  },
  module: {
    loaders: [
      // BS FA Fonts
      { test: /\.(woff|woff2)(\?v=\d+\.\d+\.\d+)?$/, loader: 'url?limit=10000&mimetype=application/font-woff' },
      { test: /\.ttf(\?v=\d+\.\d+\.\d+)?$/, loader: 'url?limit=10000&mimetype=application/octet-stream' },
      { test: /\.eot(\?v=\d+\.\d+\.\d+)?$/, loader: 'file' },
      { test: /\.svg(\?v=\d+\.\d+\.\d+)?$/, loader: 'url?limit=10000&mimetype=image/svg+xml' },
      // Style
      { test: /\.css$/, loader: "style!css" },
      // jQuery
      { test: "jquery", loader: "expose?$!expose?jQuery" },
      // HACK
      { test: require.resolve("pace-progress"), loader: "imports?define=>false" },
    ]
  },
  plugins: [
    // with the jQuery loader and externals above,
    // $, jQuery and jquery is external and available everywhere
    new webpack.ProvidePlugin({
      $: "jquery",
      jQuery: "jquery",
      "window.jQuery": "jquery"
    }),
    new webpack.optimize.CommonsChunkPlugin({
      name: "common",
      filename: "common.js",
      // all below chunks jquery, hence jquery is included in common.js
      chunks: ['include', 'a2m', 'm2a', 'index']
    }),
  ]
};
