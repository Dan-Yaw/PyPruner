#!/usr/bin/env python
# coding: utf-8

# In[10]:


import pypruner


# In[2]:

# In[11]:


pp = pypruner.Pruner("gismigrationtoolkit")


# In[16]:
pp.list_imports()

pp.list_modules


# In[19]:


pp.find_interdependencies("PortalItem", "make_artifact")

