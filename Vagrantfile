# -*- mode: ruby -*-
# vi: set ft=ruby :

Vagrant.configure("2") do |config|
    (1..2).each do |i|
        config.vm.define "node-#{i}" do |node|
            node.vm.box = "generic/ubuntu2004"
            node.vm.hostname = "node-#{i}"
        end
    end
end
