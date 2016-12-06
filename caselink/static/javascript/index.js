var Vue = require('vue');
var navBar = require('./mixins/nav-bar.js');

var vm = new Vue({
  el: "#caselink",
  mixins: [navBar],
  data: {},
  methods: {},
  watch: {},
  delimiters: ['${', '}'],
});
