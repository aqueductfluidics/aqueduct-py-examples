from aqueduct.core.aq import Aqueduct, InitParams

import template.template

params = InitParams.parse()
aq = Aqueduct(params.user_id, params.ip_address, params.port)
aq.initialize(params.init)

template.template.print_hello_world()
