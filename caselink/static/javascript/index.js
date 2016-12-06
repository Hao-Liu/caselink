var htmlify = require('./lib/htmlify.js');
var Vue = require('vue');
var _ = require('lodash');
var navBar = require('./mixins/nav-bar.js');

var vm = new Vue({
  el: "#caselink",
  mixins: [navBar],
  data: {},
  methods: {},
  watch: {},
  delimiters: ['${', '}'],
});
